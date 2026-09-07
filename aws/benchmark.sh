#!/usr/bin/env bash
# One-shot AWS GPU benchmark: launch an instance, render one 5s/768p clip, print the
# wall-clock render time, then terminate. Everything is tagged and the instance carries
# an auto-terminate fuse so a crash can't leave a GPU running.
#
#   ./benchmark.sh                 # g7e.4xlarge (Blackwell, needs G quota >= 16)
#   INSTANCE=p5.4xlarge ./benchmark.sh   # 1x H100 (needs P quota >= 16)
#
# Requires: aws cli logged in, an EC2 key pair name in KEY_NAME (optional — only needed
# if you want to SSH in; the benchmark itself reports through the instance console log).
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
INSTANCE="${INSTANCE:-g7e.4xlarge}"
IMAGE="${IMAGE:-ghcr.io/vincezh2000/minimax-h3-comfyui-serverless:cu130}"
MAX_MINUTES="${MAX_MINUTES:-75}"   # hard fuse: shutdown -h after this long, no matter what
NAME="h3-bench-$(date +%s)"

# The PyTorch DLAMIs do NOT list G7e as supported; only the "Deep Learning Base OSS
# Nvidia Driver GPU AMI" carries a driver new enough for RTX PRO 6000 Blackwell.
AMI=$(aws ssm get-parameter --region "$REGION" \
  --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id \
  --query Parameter.Value --output text)

QUOTA_CODE=L-DB2E81BA; QUOTA_LABEL="G and VT"
case "$INSTANCE" in p*) QUOTA_CODE=L-417A185B; QUOTA_LABEL="P";; esac
HAVE=$(aws service-quotas get-service-quota --region "$REGION" --service-code ec2 \
  --quota-code "$QUOTA_CODE" --query 'Quota.Value' --output text)
echo "quota (${QUOTA_LABEL} on-demand vCPU): $HAVE"
awk -v h="$HAVE" 'BEGIN{ if (h+0 < 16) { print "  need >= 16 vCPU — request not approved yet"; exit 1 } }'

echo "AMI:      $AMI"
echo "instance: $INSTANCE in $REGION"
echo "image:    $IMAGE"

# Benchmark workload: same 5s/768p/16:9 clip we already measured on RunPod (204s on H200),
# so the number is directly comparable.
WF=$(python3 - "$(dirname "$0")/../example_workflows/t2v_api.json" <<'PY'
import json, sys
wf = json.load(open(sys.argv[1]))
wf['cond']['inputs']['prompt'] = ("A cinematic shot of a corgi surfing a small wave at golden "
                                  "hour, spray glittering in the sunlight, gentle acoustic guitar.")
wf['cond']['inputs']['width'], wf['cond']['inputs']['height'] = 1344, 768
wf['cond']['inputs']['length'] = 124  # 5s at 24fps on the model's 17k+5 grid
print(json.dumps(wf))
PY
)

USERDATA=$(cat <<EOF
#!/bin/bash
exec > >(tee /var/log/bench.log|logger -t bench -s 2>/dev/console) 2>&1
shutdown -h +${MAX_MINUTES} &
set -x
nvidia-smi
cat > /tmp/wf.json <<'WFEOF'
${WF}
WFEOF
docker pull ${IMAGE}
# Serve the ComfyUI API locally so we can time a render over HTTP, exactly like production.
docker run -d --gpus all --name h3 -p 8188:8188 -e SERVE_API_LOCALLY=true ${IMAGE}
for i in \$(seq 1 120); do curl -sf localhost:8188/system_stats >/dev/null && break; sleep 10; done
curl -s localhost:8188/system_stats
python3 - <<'PY'
import json, time, urllib.request
WF = json.load(open('/tmp/wf.json'))
t0 = time.time()
pid = json.loads(urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8188/prompt', data=json.dumps({'prompt': WF}).encode(),
    headers={'Content-Type': 'application/json'})).read())['prompt_id']
while True:
    time.sleep(5)
    h = json.loads(urllib.request.urlopen(f'http://localhost:8188/history/{pid}').read())
    if h.get(pid, {}).get('status', {}).get('completed'):
        break
    if h.get(pid, {}).get('status', {}).get('status_str') == 'error':
        print('RENDER FAILED:', json.dumps(h[pid]['status'])[:2000]); raise SystemExit(1)
print(f'BENCHMARK_RESULT render_seconds={time.time()-t0:.1f} instance=${INSTANCE}')
PY
docker logs h3 --tail 40
shutdown -h now
EOF
)

echo "launching..."
IID=$(aws ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type "$INSTANCE" \
  --instance-initiated-shutdown-behavior terminate \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=200,VolumeType=gp3,Iops=6000,Throughput=500,DeleteOnTermination=true}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=purpose,Value=h3-benchmark}]" \
  --user-data "$USERDATA" \
  --query 'Instances[0].InstanceId' --output text)
echo "instance: $IID  (auto-terminates on shutdown; hard fuse ${MAX_MINUTES}m)"
echo "watch:  aws ec2 get-console-output --region $REGION --instance-id $IID --output text | grep BENCHMARK_RESULT"
echo "kill:   aws ec2 terminate-instances --region $REGION --instance-ids $IID"

#!/bin/bash
set -m  # 启用作业控制
set -e  # 如果任何命令失败，脚本退出

sed -i "s|server_url:.*|server_url:\ https://${CF_MASTER_DOMAIN}|" /etc/headscale/config.yaml
chmod 0600 /app/certs/acme.json 
sleep 5

# 启动第一个阻塞程序
python3 /opt/natter.py -m nftables -e /opt/natter-post.py -p $TRAEFIK_WEBSECURE_PORT &
pid1=$!

# 启动第二个阻塞程序
python3 /opt/natter.py -u -m nftables -e /opt/natter-post.py -p $DERP_STUN_PORT &
pid2=$!

# 启动第三个阻塞程序
python3 /opt/natter-post.py &
pid3=$!

# 捕获 SIGTERM 和 SIGINT 信号，确保清理所有子进程
trap "echo 'Stopping all processes...'; kill $pid1 $pid2 $pid3; wait" SIGTERM SIGINT

# 等待任意一个子进程退出
wait -n

# 如果某个进程退出，则终止其余进程
echo "One of the processes exited. Shutting down all processes..."
kill $pid1 $pid2 $pid3

# 等待所有进程结束后退出
wait


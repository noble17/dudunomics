#!/bin/bash
# GCP e2-micro (Ubuntu) 초기 설정 스크립트

echo "--- GCP 환경 설정 시작 ---"

# 1. Swap 메모리 설정 (1GB RAM 보완을 위해 2GB Swap 생성)
echo "1. Swap 메모리 설정 중..."
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo "Swap 설정 완료."

# 2. 필수 패키지 업데이트 및 설치
echo "2. 패키지 업데이트 및 Docker 설치 중..."
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common

# Docker 설치
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce docker-compose-plugin

# Docker 그룹에 사용자 추가 (sudo 없이 사용 가능하게)
sudo usermod -aG docker $USER

# 3. 배포 준비 완료 메시지
echo "--- 설정 완료! ---"
echo "이제 'docker-compose up -d --build' 명령어로 배포를 시작할 수 있습니다."
echo "주의: 로그아웃 후 다시 로그인해야 sudo 없이 docker 명령어를 사용할 수 있습니다."

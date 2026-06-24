#!/bin/bash

# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    build-essential libgtk2.0-dev pkg-config \
    libavcodec-dev libavformat-dev libswscale-dev \
    libgl1-mesa-dev libglfw3-dev libopencv-dev
        
sudo sh -c 'echo "${DEPS_DIR}/installed/opencv/lib" > /etc/ld.so.conf.d/opencv.conf'
sudo ldconfig

# Setup compiler
if [[ "${COMPILER_CXX}" != "" ]]; then 
    echo "CXX=${COMPILER_CXX}" >> $GITHUB_ENV
fi
if [[ "${COMPILER_CC}" != "" ]]; then 
    echo "CC=${COMPILER_CC}" >> $GITHUB_ENV
fi
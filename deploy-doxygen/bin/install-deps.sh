#!/bin/bash

# Install and download dependencies
DOXYGEN_URL="https://sourceforge.net/projects/doxygen/files/rel-${VERSION}/doxygen-${VERSION}.src.tar.gz"

sudo apt install build-essential cmake graphviz python3-pip

mkdir -p ${DEPS_DIR}/doxygen
cd ${DEPS_DIR}
wget ${DOXYGEN_URL} >/dev/null
tar --strip-components=1 -xvf *.tar.gz -C doxygen

# Installdoxygen tool
cd doxygen
mkdir -p build && cd build
cmake ..
make -j${NUM_JOBS}
sudo make install


#!/bin/bash

if [[ "${BUILD_TYPE}" == "default" ]]; then
    # Default ubuntu build
    mkdir -p ${BUILD_DIR}
    mkdir ../libs

    pushd ${BUILD_DIR}
    pwd
    cmake ${DEFAULT_CMAKE_FLAGS} ${EXTRA_CMAKE_FLAGS} \
        -DCMAKE_PREFIX_PATH="${DEPS_DIR}/installed/glog;${DEPS_DIR}/installed/protobuf;${DEPS_DIR}/installed/libzmq;${DEPS_DIR}/installed/Open3D;${DEPS_DIR}/installed/opencv" \
        .. 
    make -j${NUM_JOBS}
    popd
else
    # Docker build
    git config --global --add safe.directory ${WORK_DIR}/libaditof
    git config --global --add safe.directory ${WORK_DIR}/libaditof/glog
    git config --global --add safe.directory ${WORK_DIR}/libaditof/protobuf
    git config --global --add safe.directory ${WORK_DIR}/libaditof/libzmq
    git config --global --add safe.directory ${WORK_DIR}/libaditof/cppzmq

    project_dir=${WORK_DIR}
    pushd ${project_dir}

    GLOG_INSTALL_DIR="/aditof-deps/installed/glog"
    PROTOBUF_INSTALL_DIR="/aditof-deps/installed/protobuf"
    OPENCV_INSTALL_DIR="/aditof-deps/installed/opencv"
    LIBZMQ_INSTALL_DIR="/aditof-deps/installed/libzmq"

    mkdir -p build
    mkdir ../libs

    pushd build
    cmake .. ${DEFAULT_CMAKE_FLAGS} ${EXTRA_CMAKE_FLAGS} \
        -DCMAKE_PREFIX_PATH="${GLOG_INSTALL_DIR};${PROTOBUF_INSTALL_DIR};${LIBZMQ_INSTALL_DIR};${OPENCV_INSTALL_DIR}" \
        -DWITH_OPENCV=0
    make -j${NUM_JOBS}

    popd #build
    popd # ${project_dir}
fi

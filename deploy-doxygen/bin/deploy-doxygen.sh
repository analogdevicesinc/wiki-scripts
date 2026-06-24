#!/bin/bash

check_doxygen() {
    pushd ${WORK_DIR}/doc
    (cd build && ! make $ARGS 2>&1 | grep -E "warning:|error:") || {
        echo "Documentation incomplete or errors in the generation of it have occured!"
        exit 1
    }
    popd
    echo "Documentation was generated successfully!"
}

############################################################################
# If the current build is not a pull request and it is on main the 
# documentation will be pushed to the gh-pages branch if changes occurred
# since the last version that was pushed
############################################################################
deploy_doxygen() {
    echo "Running Github docs update on commit '$CURRENT_COMMIT'"

    git config --global user.email "cse-ci-notifications@analog.com"
    git config --global user.name "CSE-CI"
    git fetch --depth 1 origin +refs/heads/gh-pages:gh-pages
    git checkout --force gh-pages

    rm -rf ${DEPS_DIR}
    
    cp -R ${WORK_DIR}/doc/build/doxygen_doc/html/* ${WORK_DIR}
    rm -rf ${WORK_DIR}/doc

    GHPAGES_CURRENT_COMMIT=$(git log -1 --pretty=%B)
    if [[ ${GHPAGES_CURRENT_COMMIT:(-7)} != ${CURRENT_COMMIT:0:7} ]]; then
        git add --all .
        git commit --allow-empty --amend -m "Update documentation to ${CURRENT_COMMIT:0:7}"
        git push origin gh-pages -f
    else
        echo "Documentation already up to date!"
    fi
}

build_deploy_doxygen() {
    mkdir -p "${WORK_DIR}/doc"
    pushd "${WORK_DIR}/doc"
    mkdir build && cd build && cmake ..
    check_doxygen
    popd
    
    deploy_doxygen
}

build_deploy_doxygen


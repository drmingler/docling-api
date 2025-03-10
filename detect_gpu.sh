#!/bin/bash

# Script to detect GPU and select the appropriate Docker Compose file

# Check if nvidia-smi exists and can be executed
if command -v nvidia-smi >/dev/null 2>&1; then
    # Try to run nvidia-smi to check if drivers are loaded correctly
    if nvidia-smi >/dev/null 2>&1; then
        echo "NVIDIA GPU detected with working drivers."
        GPU_AVAILABLE=true
        
        # Check CUDA version
        CUDA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | cut -d'.' -f1)
        echo "CUDA compatible driver version: $CUDA_VERSION"
        
        # Check if the detected CUDA version is compatible with our requirements (CUDA 11+)
        if [ -n "$CUDA_VERSION" ] && [ "$CUDA_VERSION" -ge 11 ]; then
            echo "Using GPU configuration (CUDA $CUDA_VERSION detected)"
            COMPOSE_FILE="docker-compose.gpu.yml"
            DOCKER_BUILDKIT=1
            DOCKER_BUILD_ARGS="--build-arg CPU_ONLY=false"
            # Pass GPU capabilities to docker build
            export DOCKER_BUILDKIT=1
            export DOCKER_DEFAULT_PLATFORM=linux/amd64
            export DOCKER_CLI_EXPERIMENTAL=enabled
        else
            echo "NVIDIA GPU detected but CUDA version ($CUDA_VERSION) is too old. Minimum required: 11"
            echo "Falling back to CPU configuration."
            GPU_AVAILABLE=false
            COMPOSE_FILE="docker-compose.cpu.yml"
            DOCKER_BUILD_ARGS="--build-arg CPU_ONLY=true"
        fi
    else
        echo "NVIDIA GPU software detected but drivers may not be properly installed."
        GPU_AVAILABLE=false
        COMPOSE_FILE="docker-compose.cpu.yml"
        DOCKER_BUILD_ARGS="--build-arg CPU_ONLY=true"
    fi
else
    echo "No NVIDIA GPU detected. Using CPU configuration."
    GPU_AVAILABLE=false
    COMPOSE_FILE="docker-compose.cpu.yml"
    DOCKER_BUILD_ARGS="--build-arg CPU_ONLY=true"
fi

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    echo "ARM architecture detected. Forcing CPU mode regardless of GPU availability."
    GPU_AVAILABLE=false
    COMPOSE_FILE="docker-compose.cpu.yml"
    DOCKER_BUILD_ARGS="--build-arg CPU_ONLY=true"
fi

# Export for other scripts to use
export GPU_AVAILABLE
export COMPOSE_FILE
export DOCKER_BUILD_ARGS

echo "Selected configuration: $COMPOSE_FILE"
echo "Build arguments: $DOCKER_BUILD_ARGS"
echo "GPU_AVAILABLE=$GPU_AVAILABLE"

# If this script is being sourced, don't execute docker-compose
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    return 0
fi

# If passed arguments, run docker-compose with them
if [ $# -gt 0 ]; then
    echo "Running: docker-compose -f $COMPOSE_FILE $@"
    docker-compose -f $COMPOSE_FILE $@
else
    echo "Usage: $0 [docker-compose commands]"
    echo "or source this script to export the variables"
fi 
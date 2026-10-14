FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-ros-ign-gazebo \
      ros-humble-ros-ign-bridge \
      ros-humble-ros-ign-image \
      ros-humble-cv-bridge \
      ros-humble-image-tools \
      python3-opencv python3-numpy python3-requests \
      libgl1-mesa-dri libegl1 xvfb \
    && rm -rf /var/lib/apt/lists/*

# ソフトウェアレンダリング(GPU なしのヘッドレス実行用)
ENV LIBGL_ALWAYS_SOFTWARE=1
WORKDIR /ws
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

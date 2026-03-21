FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=unix:0
ENV QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox"

# ROS 개발 도구 설치
RUN apt-get update && apt-get install -y \
    ros-dev-tools \
    && rm -rf /var/lib/apt/lists/*

# Qt xcb 의존성 설치
RUN apt-get update && apt-get install -y \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-render-util0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    libgl1-mesa-glx \
    libegl1 \
    libfontconfig1 \
    libdbus-1-3 \
    python3-pip \
    libnss3 \
    libnspr4 \
    libxkbfile1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxtst6 \
    libxss1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 한글 폰트 설치
RUN apt-get update && apt-get install -y \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# OpenCV Qt 플러그인 충돌 방지
RUN rm -rf /usr/local/lib/python3.10/dist-packages/cv2/qt/plugins 2>/dev/null || true

# ROS workspace 복사 및 빌드
WORKDIR /root/robot
COPY src/ ./src/

RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

# 프로그램 실행
CMD ["/bin/bash", "-c", "source /opt/ros/humble/setup.bash && source /root/robot/install/setup.bash && ros2 launch robot_bringup robot_studio.launch.py"]
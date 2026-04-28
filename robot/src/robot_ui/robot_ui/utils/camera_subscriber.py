import numpy as np
from PySide6.QtCore import Signal, QObject

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class ImageSignal(QObject):
    """ROS2 콜백에서 Qt 메인 스레드로 이미지 전달"""
    image_received = Signal(str, np.ndarray)


class CameraSubscriberNode(Node):
    """ROS2 카메라 토픽 구독 노드"""

    def __init__(self, signal: ImageSignal):
        super().__init__('camera_preview_node')
        self.signal = signal
        self.bridge = CvBridge()
        self.subscriptions_dict = {}

    def subscribe_to_topic(self, topic_name: str):
        if topic_name in self.subscriptions_dict:
            return

        def callback(msg: Image):
            try:
                cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
                self.signal.image_received.emit(topic_name, cv_image)
            except Exception as e:
                self.get_logger().error(f'Failed to convert image: {e}')

        sub = self.create_subscription(Image, topic_name, callback, 10)
        self.subscriptions_dict[topic_name] = sub
        self.get_logger().info(f'Subscribed to {topic_name}')

    def unsubscribe_from_topic(self, topic_name: str):
        if topic_name in self.subscriptions_dict:
            self.destroy_subscription(self.subscriptions_dict[topic_name])
            del self.subscriptions_dict[topic_name]

    def get_available_image_topics(self) -> list[str]:
        topics = self.get_topic_names_and_types()
        image_topics = []
        for name, types in topics:
            if 'sensor_msgs/msg/Image' in types:
                # 실제 publisher가 있는지 확인
                publishers = self.get_publishers_info_by_topic(name)
                if len(publishers) > 0:
                    image_topics.append(name)
        return image_topics

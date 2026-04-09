import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        # 파라미터로 카메라 ID 받기
        self.declare_parameter('camera_id', 0)
        self.declare_parameter('topic_name', 'image_raw')

        self.camera_id = self.get_parameter('camera_id').get_parameter_value().integer_value
        topic_name = self.get_parameter('topic_name').get_parameter_value().string_value

        self.cap = None
        self.publisher = self.create_publisher(Image, topic_name, 10)
        self.bridge = CvBridge()

        self._retry_interval = 2.0  # 카메라 재연결 시도 간격 (초)
        self._last_retry_time = 0.0

        self.timer = self.create_timer(0.033, self.timer_callback) # 30 FPS

    def _open_camera(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.camera_id)
        return self.cap.isOpened()

    def timer_callback(self):
        if self.cap is None or not self.cap.isOpened():
            now = self.get_clock().now().nanoseconds / 1e9
            if now - self._last_retry_time >= self._retry_interval:
                self._last_retry_time = now
                if self._open_camera():
                    self.get_logger().info(f'Camera {self.camera_id} reopened successfully')
                else:
                    self.get_logger().warn(f'Camera {self.camera_id} not available, retrying in {self._retry_interval}s')
            return

        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8') # OpenCV 기본 색상 형식 사용
            self.publisher.publish(msg)
        else:
            self.get_logger().warn(f'Camera {self.camera_id} read failed, will retry in {self._retry_interval}s')
            self.cap.release()
            self.cap = None
            self._last_retry_time = self.get_clock().now().nanoseconds / 1e9

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


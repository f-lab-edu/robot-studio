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

        self.timer = self.create_timer(0.04, self.timer_callback) # 25 FPS

    def _open_camera(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.camera_id)
        return self.cap.isOpened()

    def timer_callback(self):
        if self.cap is None or not self.cap.isOpened():
            if self._open_camera():
                self.get_logger().info(f'Camera {self.camera_id} opened successfully')
            return

        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8') # OpenCV 기본 색상 형식 사용
            self.publisher.publish(msg)
        else:
            self.get_logger().error('Failed to capture image from camera')
            self.cap.release()
            self.cap = None

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String

JOINT_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']


class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop_node')

        self._active = False

        self._sub_leader = self.create_subscription(
            JointState, '/leader/joint_states', self._on_leader, 10)
        self._sub_command = self.create_subscription(
            Bool, '/teleop/command', self._on_command, 10)

        self._pub_follower = self.create_publisher(JointState, '/follower/joint_command', 10)
        self._pub_status = self.create_publisher(String, '/teleop/status', 10)

        self._pub_status.publish(String(data='idle'))

    def _on_command(self, msg: Bool):
        self._active = msg.data
        status = 'active' if self._active else 'idle'
        self._pub_status.publish(String(data=status))
        self.get_logger().info(f'Teleop {status}')

    def _on_leader(self, msg: JointState):
        if not self._active:
            return

        out = JointState()
        out.header.stamp = self.get_clock().now().to_msg()
        out.name = JOINT_NAMES
        out.position = list(msg.position[:6])
        self._pub_follower.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

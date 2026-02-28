import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from st3215 import ST3215

JOINT_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']
SERVO_IDS = [1, 2, 3, 4, 5, 6]


class LeaderArmNode(Node):
    def __init__(self):
        super().__init__('leader_arm_node')

        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('frequency', 30.0)

        self._pub_joints = self.create_publisher(JointState, '/leader/joint_states', 10)
        self._pub_status = self.create_publisher(String, '/leader/connection_status', 10)

        self._bus: ST3215 | None = None
        self._connected = False

        freq = self.get_parameter('frequency').value
        self._timer = self.create_timer(1.0 / freq, self._timer_callback)

        self.add_on_set_parameters_callback(self._on_params_changed)

    def _on_params_changed(self, params):
        for param in params:
            if param.name == 'port':
                self.get_logger().info(f'Port changed to {param.value}, reconnecting...')
                self._close_bus()
        return SetParametersResult(successful=True)

    def _open_bus(self):
        port = self.get_parameter('port').value
        try:
            bus = ST3215(port)
            if all(bus.PingServo(i) for i in SERVO_IDS):
                self._bus = bus
                self._connected = True
                self._pub_status.publish(String(data='connected'))
                self.get_logger().info(f'Leader arm connected on {port}')
            else:
                self.get_logger().warn(f'Some servos did not respond on {port}')
                self._pub_status.publish(String(data='disconnected'))
        except Exception as e:
            self.get_logger().warn(f'Leader arm open failed: {e}')
            self._pub_status.publish(String(data='disconnected'))

    def _close_bus(self):
        self._bus = None
        self._connected = False
        self._pub_status.publish(String(data='disconnected'))

    def _timer_callback(self):
        if not self._connected:
            self._open_bus()
            return

        try:
            positions = [float(self._bus.ReadPosition(i)) for i in SERVO_IDS]
            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.name = JOINT_NAMES
            msg.position = positions
            self._pub_joints.publish(msg)
        except Exception as e:
            self.get_logger().error(f'Leader arm read error: {e}')
            self._close_bus()


def main(args=None):
    rclpy.init(args=args)
    node = LeaderArmNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from st3215 import ST3215

JOINT_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']
SERVO_IDS = [1, 2, 3, 4, 5, 6]
POS_MIN = 0
POS_MAX = 4095
LEADER_HZ = 30.0


class FollowerArmNode(Node):
    def __init__(self, **kwargs):
        super().__init__('follower_arm_node', **kwargs)

        self.declare_parameter('port', '/dev/ttyACM1')

        self._sub_cmd = self.create_subscription(
            JointState, '/follower/joint_command', self._on_command, 10)
        self._sub_teleop = self.create_subscription(
            String, '/teleop/status', self._on_teleop_status, 10)
        self._pub_joints = self.create_publisher(JointState, '/follower/joint_states', 10)
        self._pub_status = self.create_publisher(String, '/follower/connection_status', 10)

        self._bus: ST3215 | None = None
        self._connected = False
        self._current_positions = [2048.0] * 6

        self._timer = self.create_timer(1.0 / LEADER_HZ, self._feedback_callback)  # 30 Hz

        self.add_on_set_parameters_callback(self._on_params_changed)

    def _on_teleop_status(self, msg: String):
        if not self._connected:
            return
        try:
            if msg.data == 'active':
                for i in SERVO_IDS:
                    self._bus.StartServo(i)
            else:
                for i in SERVO_IDS:
                    self._bus.StopServo(i)
        except Exception as e:
            self.get_logger().error(f'Torque toggle error: {e}')

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
                for i in SERVO_IDS:
                    bus.StopServo(i)
                    bus.SetMode(i, 0)
                    bus.SetAcceleration(i, 0)
                self._bus = bus
                self._connected = True
                self._pub_status.publish(String(data='connected'))
                self.get_logger().info(f'Follower arm connected on {port}')
            else:
                self.get_logger().warn(f'Some servos did not respond on {port}')
                self._pub_status.publish(String(data='disconnected'))
        except Exception as e:
            self.get_logger().warn(f'Follower arm open failed: {e}')
            self._pub_status.publish(String(data='disconnected'))

    def _close_bus(self):
        if self._bus is not None:
            try:
                for i in SERVO_IDS:
                    self._bus.StopServo(i)
            except Exception:
                pass
        self._bus = None
        self._connected = False
        self._pub_status.publish(String(data='disconnected'))

    def _on_command(self, msg: JointState):
        if not self._connected:
            return

        try:
            for idx, (servo_id, pos) in enumerate(zip(SERVO_IDS, msg.position)):
                pos_clamped = max(POS_MIN, min(POS_MAX, int(pos)))
                distance = abs(pos_clamped - self._current_positions[idx])
                if distance == 0:
                    continue
                speed = int(distance * LEADER_HZ)
                self._bus.SetSpeed(servo_id, speed)
                self._bus.WritePosition(servo_id, pos_clamped)
        except Exception as e:
            self.get_logger().error(f'Follower arm write error: {e}')
            self._close_bus()

    def _feedback_callback(self):
        if not self._connected:
            self._open_bus()
            return

        try:
            positions = [float(self._bus.ReadPosition(i)) for i in SERVO_IDS]
            self._current_positions = positions
            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.name = JOINT_NAMES
            msg.position = positions
            self._pub_joints.publish(msg)
        except Exception as e:
            self.get_logger().error(f'Follower arm feedback error: {e}')
            self._close_bus()


def main(args=None):
    rclpy.init(args=args)
    node = FollowerArmNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

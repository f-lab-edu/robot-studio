from setuptools import setup, find_packages

package_name = 'robot_ui'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'aiohttp', 'qasync', 'PySide6-WebEngine'],
    zip_safe=True,
    maintainer='User',
    maintainer_email='user@example.com',
    description='Robot Studio UI',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ui = robot_ui.main:main',
        ],
    },
)

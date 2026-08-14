import numpy as np
from PyQt5.QtCore import Qt
from pyqtgraph.opengl import GLViewWidget, GLGridItem, GLLinePlotItem, GLMeshItem
from pyqtgraph.opengl.MeshData import MeshData


class KneeOrientationViewer(GLViewWidget):
    """OpenGL viewer for the thigh/calf orientation in 3D."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCameraPosition(distance=8, elevation=12, azimuth=45)
        self.setBackgroundColor((0.07, 0.11, 0.18, 1.0))
        self.setWindowTitle("3D Knee Viewer")

        self._build_scene()

    def _build_scene(self):
        grid = GLGridItem(color=(0.35, 0.45, 0.6, 0.7))
        grid.setSize(6, 6, 6)
        grid.setSpacing(1, 1, 1)
        self.addItem(grid)

        self._axis_x = GLLinePlotItem(pos=np.array([[0, 0, 0], [2.0, 0, 0]], dtype=np.float32), color=(1, 0, 0, 1), width=3, antialias=True)
        self._axis_y = GLLinePlotItem(pos=np.array([[0, 0, 0], [0, 2.0, 0]], dtype=np.float32), color=(0, 1, 0, 1), width=3, antialias=True)
        self._axis_z = GLLinePlotItem(pos=np.array([[0, 0, 0], [0, 0, 2.0]], dtype=np.float32), color=(0, 0, 1, 1), width=3, antialias=True)
        self.addItem(self._axis_x)
        self.addItem(self._axis_y)
        self.addItem(self._axis_z)

        self.thigh_mesh = self._make_segment((0.22, 0.55, 0.95, 1.0), length=2.2, width=0.35, height=0.35)
        self.calf_mesh = self._make_segment((0.95, 0.45, 0.15, 1.0), length=2.0, width=0.28, height=0.28)
        self.addItem(self.thigh_mesh)
        self.addItem(self.calf_mesh)

        self.thigh_mesh.translate(0.0, 0.0, 0.0)
        self.calf_mesh.translate(0.0, 0.0, 0.0)

    def _make_segment(self, color, length=2.0, width=0.25, height=0.25):
        half_l = length / 2.0
        vertices = np.array([
            [-width / 2, -height / 2, -half_l],
            [ width / 2, -height / 2, -half_l],
            [ width / 2,  height / 2, -half_l],
            [-width / 2,  height / 2, -half_l],
            [-width / 2, -height / 2,  half_l],
            [ width / 2, -height / 2,  half_l],
            [ width / 2,  height / 2,  half_l],
            [-width / 2,  height / 2,  half_l],
        ], dtype=np.float32)
        faces = np.array([
            [0, 1, 2], [0, 2, 3],
            [4, 6, 5], [4, 7, 6],
            [0, 4, 5], [0, 5, 1],
            [1, 5, 6], [1, 6, 2],
            [2, 6, 7], [2, 7, 3],
            [3, 7, 4], [3, 4, 0],
        ], dtype=np.uint32)
        meshdata = MeshData(vertexes=vertices, faces=faces)
        return GLMeshItem(meshdata=meshdata, smooth=True, color=color, shader='shaded', glOptions='opaque')

    def update_orientation(self, pitch: float, roll: float, yaw: float):
        self.thigh_mesh.resetTransform()
        self.calf_mesh.resetTransform()

        self.thigh_mesh.translate(0.0, 0.0, 0.0)
        self.calf_mesh.translate(0.0, 0.0, 0.0)

        self.thigh_mesh.rotate(pitch, 1, 0, 0)
        self.thigh_mesh.rotate(roll, 0, 1, 0)
        self.thigh_mesh.rotate(yaw, 0, 0, 1)

        self.calf_mesh.rotate(pitch, 1, 0, 0)
        self.calf_mesh.rotate(roll, 0, 1, 0)
        self.calf_mesh.rotate(yaw, 0, 0, 1)
        self.calf_mesh.translate(0.0, 0.0, 1.7)

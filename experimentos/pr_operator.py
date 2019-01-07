import bpy
from bpy.types import Operator

from bpy_extras.view3d_utils import region_2d_to_location_3d
from bpy_extras.view3d_utils import region_2d_to_origin_3d

import bgl
import blf
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader

import mathutils


class OT_draw_operator(Operator):
    bl_idname = "object.draw_op"
    bl_label = "Draw Operator"
    bl_description = "Operator for drawing"
    bl_options = {'REGISTER'}

    def __init__(self):
        self.draw_handle_2d = None
        self.draw_handle_3d = None
        self.draw_event = None
        self.mouse_vert = None
        self.extruding = False

        self.vertices = []
        self.create_batch()

    def invoke(self, context, event):
        args = (self, context)
        self.register_handlers(args, context)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def register_handlers(self, args, context):
        self.draw_handle_3d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_3d, args, "WINDOW", "POST_VIEW")

        self.draw_handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_2d, args, "WINDOW", "POST_PIXEL")

        self.draw_event = context.window_manager.event_timer_add(
            0.1, window=context.window)

    def unregister_handlers(self, context):
        context.window_manager.event_timer_remove(self.draw_event)
        bpy.types.SpaceView3D.draw_handler_remove(
            self.draw_handle_3d, "WINDOW")
        bpy.types.SpaceView3D.draw_handler_remove(
            self.draw_handle_2d, "WINDOW")

        self.draw_handle_2d = None
        self.draw_handle_3d = None
        self.draw_event = None

    def get_snap_vertex_indizes(self, view_rot):

        v1 = round(abs(view_rot[0]), 3)
        v2 = round(abs(view_rot[1]), 3)

        if v1 == 0.5 and v2 == 0.5:
            return (1, 2)
        if (v1 == 0.707 and v2 == 0.707) or (v1 == 0.0 and v2 == 0.0):
            return (0, 2)
        return None

    def get_mouse_3d_vertex(self, event, context):
        x, y = event.mouse_region_x, event.mouse_region_y

        region = context.region
        rv3d = context.space_data.region_3d
        view_rot = rv3d.view_rotation

        dir = view_rot @ mathutils.Vector((0, 0, -1))

        dir = dir.normalized() * -2.0

        vec = region_2d_to_location_3d(region, rv3d, (x, y), dir)

        if not rv3d.is_perspective:
            ind = self.get_snap_vertex_indizes(view_rot)
            if ind is not None:
                vec[ind[0]] = vec[ind[0]] - vec[ind[0]] % 0.1
                vec[ind[1]] = vec[ind[1]] - vec[ind[1]] % 0.1
        return vec

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        if event.type in {'ESC'}:
            print('al menos esc funciona')
            self.unregister_handlers(context)

            return {'CANCELLED'}

        if event.type in {'MOUSEMOVE'} and not self.extruding:

            if len(self.vertices) > 0:
                self.mouse_vert = self.get_mouse_3d_vertex(event, context)
                self.create_batch()

        if event.value == "PRESS":
            if event.type == "LEFTMOUSE" and not self.extruding:
                vertex = self.get_mouse_3d_vertex(event, context)
                self.vertices.append(vertex)
                self.create_batch()

            if event.type == "RET" and not self.extruding:
                print('hola en evento return not extruding')
                self.create_object(context)
                return {'RUNNING_MODAL'}

            if event.type == "RET" and self.extruding:
                self.unregister_handlers(context)
                return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def create_object(self, context):
        mesh = bpy.data.meshes.new('MY_MESH')
        obj = bpy.data.objects.new('obj', mesh)

        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(state=True)

        bm = bmesh.new()

        for v in self.vertices:
            bm.verts.new(v)

        bm.to_mesh(mesh)
        bm.free()

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        self.extruding = True
        context.area.tag_redraw()
        bpy.ops.mesh.edge_face_add()
        bpy.ops.mesh.extrude_region_move()
        bpy.ops.transform.translate('INVOKE_DEFAULT', constraint_axis=(
            False, False, True), constraint_orientation='NORMAL')

        # bpy.ops.object.mode_set(mode='OBJECT')
        # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')

    def finish(self, context):
        self.unregister_handlers(context)
        return {'FINISHED'}

    def create_batch(self):
        points = self.vertices.copy()

        if self.mouse_vert is not None:
            points.append(self.mouse_vert)

        self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        self.batch = batch_for_shader(
            self.shader, 'LINE_STRIP', {"pos": points})

    def draw_callback_2d(self, op, context):
        region = context.region
        text = 'Draw mode active'

        subtext = "Esc : Close | Enter : Create"

        xt = int(region.width / 2)

        blf.size(0, 24, 72)
        blf.position(0, xt - blf.dimensions(0, text)[0] / 2, 60, 0)
        blf.draw(0, text)

        blf.size(1, 20, 72)
        blf.position(1, xt - blf.dimensions(0, subtext)[0] / 2, 30, 1)
        blf.draw(1, subtext)

    def draw_callback_3d(self, op, context):
        bgl.glLineWidth(5)
        self.shader.bind()
        self.shader.uniform_float("color", (0.1, 0.3, 0.7, 0.6))

        self.batch.draw(self.shader)


def register():
    bpy.utils.register_class(OT_draw_operator)


def unregister():
    bpy.utils.unregister_class(OT_draw_operator)


if __name__ == "__main__":
    register()

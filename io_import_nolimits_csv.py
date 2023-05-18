# <pep8 compliant>
from contextvars import Token

TOOL_NAME = "NoLimits 2 Professional Track Data (.csv)"

bl_info = {
    "name": "NoLimits 2 Professional Track Data (.csv)",
    "author": "Daniel Hilpert",
    "version": (3, 0, 1),
    "blender": (2, 80, 0),
    "location": "File > Import > NoLimits 2 Professional Track Data (.csv)",
    "description": "Generates a curve object from NoLimits 2 Roller Coaster "
                   "Simulation Professional CSV data",
    "wiki_url": "https://github.com/bestdani/BlenderNoLimitsCSVImporter",
    "category": "Import-Export"
}

import csv
import pathlib

import bpy
import mathutils
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper

TO_BLENDER_COORDINATES = mathutils.Matrix(
    ((1.0, 0.0, 0.0),
     (0.0, 0.0, -1.0),
     (0.0, 1.0, 0.0))
)


def get_vertices_from_csv(file_path):
    vertices = []

    with open(file_path, 'r') as csv_file:
        treader = csv.reader(csv_file, delimiter='\t', quotechar='|')
        for row in treader:
            try:
                vertices.append(
                    {
                        'pos': mathutils.Vector(
                            (float(row[1]), float(row[2]), float(row[3]))
                        ),
                        'front': mathutils.Vector(
                            (float(row[4]), float(row[5]), float(row[6]))
                        ),
                        'left': mathutils.Vector(
                            (float(row[7]), float(row[8]), float(row[9]))
                        ),
                        'up': mathutils.Vector(
                            (float(row[10]), float(row[11]), float(row[12]))
                        )
                    }
                )
            except ValueError:
                continue

    return vertices


def apply_vertex_positions(spline, vertices):
    for i, vertex in enumerate(vertices):
        new_point = spline.points[i]
        new_point.co = (TO_BLENDER_COORDINATES @ vertex['pos']).to_4d()


def create_tmp_reader(context, target_object):
    reader = bpy.data.objects.new('tmp_curve_reader', None)
    reader.empty_display_type = 'ARROWS'
    context.layer_collection.collection.objects.link(reader)
    constraint = reader.constraints.new('FOLLOW_PATH')
    constraint.target = target_object
    constraint.use_curve_follow = True
    constraint.use_fixed_location = True
    return constraint, reader


def apply_tilt_values(context, vertices, target_object, spline_points):
    point_count = len(vertices)
    largest_index = point_count - 1

    constraint, reader = create_tmp_reader(context, target_object)

    for i in range(point_count):
        constraint.offset_factor = i / largest_index

        dg = bpy.context.evaluated_depsgraph_get()
        bpy.context.scene.frame_current = 1

        eval_reader = reader.evaluated_get(dg)
        matrix = eval_reader.matrix_world.copy()

        evaluated_up = matrix.col[2].xyz
        expected_up = TO_BLENDER_COORDINATES @ vertices[i]['up']
        expected_forward = TO_BLENDER_COORDINATES @ vertices[i]['front']

        calculated_forward = evaluated_up.cross(expected_up)
        forward_direction = calculated_forward @ expected_forward

        tilt_angle = expected_up.angle(evaluated_up)
        if forward_direction < 0:
            tilt_angle *= -1

        spline_points[i].tilt = tilt_angle

    bpy.data.objects.remove(reader, do_unlink=True)


def create_empties(context, name: str, vertices, parent_object):
    collection = bpy.data.collections.new(name)
    context.scene.collection.children.link(collection)

    for vertex in vertices:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = 'ARROWS'

        matrix_nl2 = mathutils.Matrix().to_3x3()
        matrix_nl2.col[0] = vertex['left']
        matrix_nl2.col[1] = vertex['up']
        matrix_nl2.col[2] = vertex['front']

        matrix_blender = (TO_BLENDER_COORDINATES @ matrix_nl2).to_4x4()
        matrix_blender.col[3] = (
                TO_BLENDER_COORDINATES @ vertex['pos']).to_4d()

        obj.matrix_world = matrix_blender

        collection.objects.link(obj)


def add_curve_from_csv(context, file_path: str, import_raw_points: bool):
    file_path = pathlib.Path(file_path)
    name = file_path.stem

    vertices = get_vertices_from_csv(file_path)

    curve_data = bpy.data.curves.new(name, 'CURVE')
    curve_data.twist_mode = 'MINIMUM'
    curve_data.dimensions = '3D'

    spline = curve_data.splines.new('POLY')
    spline.resolution_u = 1
    spline.tilt_interpolation = 'LINEAR'
    spline.points.add(len(vertices) - 1)

    apply_vertex_positions(spline, vertices)

    curve_object = bpy.data.objects.new(name + " Object", curve_data)
    curve_object.location = (0, 0, 0)

    if import_raw_points:
        create_empties(context, name + " Raw", vertices, curve_object)

    context.scene.collection.objects.link(curve_object)
    apply_tilt_values(context, vertices, curve_object, spline.points)

    return {'FINISHED'}


def sample_curve_as_csv(context, file_path, point_count):
    file_path = pathlib.Path(file_path)
    curve = context.active_object
    if not curve or curve.type != 'CURVE':
        return {'CANCELLED'}

    point_count = len(curve.data.splines[0].points) if point_count == 0 \
        else point_count
    largest_index = point_count - 1
    constraint, reader = create_tmp_reader(context, curve)

    matrices = []
    for i in range(point_count):
        offset = i / largest_index
        constraint.offset_factor = offset
        dg = bpy.context.evaluated_depsgraph_get()
        bpy.context.scene.frame_current = 1
        eval_reader = reader.evaluated_get(dg)
        matrices.append(eval_reader.matrix_world.copy())

    bpy.data.objects.remove(reader, do_unlink=True)

    csv_header = '"No."\t"PosX"\t"PosY"\t"PosZ"\t' \
                 '"FrontX"\t"FrontY"\t"FrontZ"\t' \
                 '"LeftX"\t"LeftY"\t"LeftZ"\t' \
                 '"UpX"\t"UpY"\t"UpZ"'

    csv_rows = [csv_header]
    for i, m in enumerate(matrices):
        pos = m.col[3]
        up = m.col[2]
        csv_rows.append(
            f'{i + 1}\t{pos.x}\t{pos.z}\t{-pos.y}'
            f'\t0.0\t0.0\t0.0\t0.0\t0.0\t0.0\t'
            f'{up.x}\t{up.z}\t{-up.y}'
        )

    csv_content = '\n'.join(csv_rows)
    with open(file_path.with_suffix('.csv'), 'w') as f:
        f.write(csv_content)

    return {'FINISHED'}


class ImportNl2Csv(Operator, ImportHelper):
    """Imports coaster track splines as a curve"""
    bl_idname = "import_nl.csv_data"
    bl_label = TOOL_NAME

    filename_ext = ".csv"

    filter_glob: StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )

    import_raw_points: BoolProperty(
        default=False,
        name="Import Raw Points (slow!)",
        description="Imports the raw points as empties. Attention, this can take several minutes for many vertices!",
    )

    def execute(self, context):
        return add_curve_from_csv(
            context, self.filepath, self.import_raw_points
        )


class ExportNl2Csv(Operator, ExportHelper):
    """Exports the active curve as a NoLimits 2 Professional compatible CSV
    file"""
    bl_idname = "export_nl.csv_data"
    bl_label = TOOL_NAME

    filename_ext = ".csv"

    point_count: IntProperty(
        name="Point Count",
        default=0,
        min=0,
    )

    filter_glob: StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        result = sample_curve_as_csv(context, self.filepath, self.point_count)
        if result != {'FINISHED'}:
            self.report(
                {'ERROR_INVALID_CONTEXT'}, 'No valid curve object selected'
            )
        return result


def menu_func_import(self, context):
    self.layout.operator(
        ImportNl2Csv.bl_idname,
        text=ImportNl2Csv.bl_label
    )


def menu_func_export(self, context):
    self.layout.operator(
        ExportNl2Csv.bl_idname,
        text=ExportNl2Csv.bl_label
    )


def register():
    bpy.utils.register_class(ImportNl2Csv)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(ExportNl2Csv)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ImportNl2Csv)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ExportNl2Csv)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
    bpy.ops.import_nl.csv_data('INVOKE_DEFAULT')

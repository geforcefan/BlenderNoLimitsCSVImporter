# <pep8 compliant>

IMPORTER_NAME = "NoLimits 2 Professional Track Data (.csv)"

bl_info = {
    "name": "NoLimits 2 Professional Track Data (.csv)",
    "author": "Daniel Hilpert",
    "version": (2, 80, 1),
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
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

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


def add_curve_from_csv(context, file_path):
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

    context.scene.collection.objects.link(curve_object)
    apply_tilt_values(context, vertices, curve_object, spline.points)

    return {'FINISHED'}


class ImportNl2Csv(Operator, ImportHelper):
    """Imports coaster track splines as a curve"""
    bl_idname = "import_nl.csv_data"
    bl_label = IMPORTER_NAME

    filename_ext = ".csv"

    filter_glob: StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        return add_curve_from_csv(context, self.filepath)


def menu_func_import(self, context):
    self.layout.operator(
        ImportNl2Csv.bl_idname,
        text=ImportNl2Csv.bl_label
    )


def register():
    bpy.utils.register_class(ImportNl2Csv)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportNl2Csv)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
    bpy.ops.import_nl.csv_data('INVOKE_DEFAULT')

# <pep8 compliant>

IMPORTER_NAME = "NoLimits 2 Professional Track Spline (.csv)"

bl_info = {
    "name": "NoLimits 2 Professional Track Spline (.csv)",
    "author": "Ercan Akyürek and Daniel Hilpert",
    "version": (2, 80, 1),
    "blender": (2, 80, 0),
    "location": "File > Import > NoLimits 2 Professional Track Spline (.csv)",
    "description": "Generates a curve object from NoLimits 2 Roller Coaster "
                   "Simulation Professional CSV data",
    "wiki_url": "https://github.com/bestdani/BlenderNoLimitsCSVImporter",
    "category": "Import-Export"
}

import bpy
import csv
import math
import pathlib

import mathutils
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from bpy_extras.object_utils import object_data_add


def get_vertices_from_csv(file_path):
    vertices = []

    with open(file_path, 'r') as csv_file:
        treader = csv.reader(csv_file, delimiter='\t', quotechar='|')
        for row in treader:
            try:
                vertices.append({
                    'pos': mathutils.Vector(
                        (float(row[1]), float(row[2]), float(row[3]))),
                    'front': mathutils.Vector(
                        (float(row[4]), float(row[5]), float(row[6]))),
                    'left': mathutils.Vector(
                        (float(row[7]), float(row[8]), float(row[9]))),
                    'up': mathutils.Vector(
                        (float(row[10]), float(row[11]), float(row[12])))
                })
            except ValueError:
                continue

    return vertices


def add_curve_from_csv(context, file_path):
    file_path = pathlib.Path(file_path)

    vertices = get_vertices_from_csv(file_path)

    name = file_path.stem
    curve_data = bpy.data.curves.new(name, 'CURVE')
    curve_data.twist_mode = 'Z_UP'

    curve_data.dimensions = '3D'
    spline = curve_data.splines.new('NURBS')

    spline.tilt_interpolation = 'BSPLINE'
    spline.points.add(len(vertices) - 1)

    apply_tilt(spline, vertices)

    curve_object = bpy.data.objects.new(name + " Object", curve_data)
    curve_object.location = (0, 0, 0)

    object_data_add(context, curve_data)

    return {'FINISHED'}


def apply_tilt(spline, vertices):
    i = 0
    last_roll = 0
    roll_to_add = 0
    for vertex in vertices:
        new_point = spline.points[i]
        x, z, y = vertex['pos']

        new_point.co = (x * -1, y, z, 1)

        actual_roll = math.atan2(-vertex['left'][1], vertex['up'][1])
        diff = last_roll - actual_roll
        last_roll = actual_roll

        if math.fabs(diff) >= 358 * math.pi / 180:
            roll_to_add = roll_to_add + diff

        roll = roll_to_add + actual_roll

        new_point.tilt = -roll

        i = i + 1


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.

class ImportNl2Csv(Operator, ImportHelper):
    """Imports coaster track splines as a curve"""
    bl_idname = "import_nl.csv_data"
    bl_label = IMPORTER_NAME

    # ImportHelper mixin class uses this
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

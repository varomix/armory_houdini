import io
import os
import struct
import threading
import subprocess
import json

import hou
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWebEngineWidgets import *
import PySide2

class ArmoryHoudini(QWidget):

    def __init__(self):
        super(ArmoryHoudini, self).__init__()

        # ui = self.onCreateInterface()
        print "Let's get armored by "
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        # self.layout.addWidget(ui)
        self.textBox = QTextEdit("/home/varomix/bin/ArmorySDK1911/ArmorySDK")
        self.button = QPushButton("Armory Play")
        self.layout.addWidget(self.textBox)
        self.layout.addWidget(self.button)

        self.button.clicked.connect(self.armory_play)
        # self.layout.addWidget(QPushButton("hello"))

        self.setLayout(self.layout)

    def sdk_path(self):
        # Enter path to armsdk in the textBox
        # global textBox
        return str(self.textBox.toPlainText()).replace('\\', '/')

    def hip_path(self):
        # Project location
        return os.path.dirname(hou.hipFile.path())

    def hip_name(self):
        # Project file name
        return hou.hipFile.basename().split('.')[0]

    def build_dir(self):
        # Build directory name
        return 'build_' + self.hip_name()

    def fp_build(self):
        # Path to build directory
        return self.hip_path() + '/' + self.build_dir()

    def write_arm(self, filepath, output):
        # Save data into .arm file
        with open(filepath, 'wb') as f:
            f.write(self.packb(output))
        # with open(filepath + '_debug.json', 'w') as f:
        # f.write(json.dumps(output, sort_keys=True, indent=4))

    def run_thread(self, cmd, done):
        def fn():
            subprocess.Popen(cmd).wait()
            done()
            return

        threading.Thread(target=fn).start()

    def write_matrix(self, m):
        # Write hou.Matrix4 into a float array
        return [m.at(0, 0), m.at(1, 0), m.at(2, 0), m.at(3, 0), \
                m.at(0, 1), m.at(1, 1), m.at(2, 1), m.at(3, 1), \
                m.at(0, 2), m.at(1, 2), m.at(2, 2), m.at(3, 2), \
                m.at(0, 3), m.at(1, 3), m.at(2, 3), m.at(3, 3)]

    def write_material(self, matnode):
        # ! Assume principled shader
        # print 'matnode', matnode
        mat = {}
        mat['name'] = matnode.name()
        mat['shader'] = matnode.name() + '_data.arm/' + matnode.name() + '_data'
        mat['contexts'] = []
        con = {}
        mat['contexts'].append(con)
        con['name'] = 'mesh'
        con['bind_textures'] = []
        con['bind_constants'] = []

        m = {}
        m['shader_datas'] = []
        sd = {}
        m['shader_datas'].append(sd)
        sd['name'] = matnode.name() + '_data'
        sd['contexts'] = []
        c = {}
        sd['contexts'].append(c)
        c['name'] = 'mesh'
        c['compare_mode'] = 'less'
        c['cull_mode'] = 'none'
        # c['cull_mode'] = 'clockwise'
        c['depth_write'] = True
        c['texture_units'] = []
        c['vertex_shader'] = matnode.name() + '_mesh.vert'
        c['fragment_shader'] = matnode.name() + '_mesh.frag'
        c['vertex_structure'] = [{'name': 'pos', 'size': 3}, {'name': 'nor', 'size': 3}]
        c['constants'] = [{'name': 'WVP', 'type': 'mat4', 'link': '_worldViewProjectionMatrix'}, \
                          {'name': 'N', 'type': 'mat3', 'link': '_normalMatrix'}]

        out_path = self.fp_build() + '/compiled/Assets/' + matnode.name() + '_data.arm'
        self.write_arm(out_path, m)

        # Default vertex shader
        vs = """#version 450
in vec3 pos;
in vec3 nor;
uniform mat4 WVP;
uniform mat3 N;
out vec3 wnormal;
void main() {
    vec4 spos = vec4(pos, 1.0);
    wnormal = normalize(N * nor);
    gl_Position = WVP * spos;
}
    """

        # Default fragment shader
        basecol = matnode.evalParmTuple('basecolor')
        fs = """#version 450
in vec3 wnormal;
out vec4 fragColor;
void main() {
    vec3 n = normalize(wnormal);
    vec3 l = vec3(0.3, 1.0, 0.6);
    vec3 basecol = vec3""" + str(basecol) + """;
    fragColor = vec4(basecol * clamp(dot(n, l), 0.0, 1.0) + vec3(0.1, 0.1, 0.1), 1.0);
}
    """

        # Write shaders
        out_path = self.fp_build() + '/compiled/Shaders/' + matnode.name() + '_mesh'
        with open(out_path + '.vert.glsl', 'w') as f:
            f.write(vs)
        with open(out_path + '.frag.glsl', 'w') as f:
            f.write(fs)

        return mat

    def write_mesh(self, objnode, raw):
        # Write mesh data of current object
        md = {}
        raw['mesh_datas'].append(md)
        md['name'] = objnode.name() + '_data'
        md['vertex_arrays'] = []
        md['index_arrays'] = []
        # Position array
        pa = {}
        pa['attrib'] = 'pos'
        pa['values'] = []
        md['vertex_arrays'].append(pa)
        # Normal array
        na = {}
        na['attrib'] = 'nor'
        na['values'] = []
        md['vertex_arrays'].append(na)
        # Index array
        ia = {}
        ia['material'] = 0
        ia['values'] = []
        md['index_arrays'].append(ia)

        def write_vert(pos, nor):
            # Store position and normal into vertex arrays
            pa['values'].append(pos.x())
            pa['values'].append(pos.y())
            pa['values'].append(pos.z())
            na['values'].append(nor.x())
            na['values'].append(nor.y())
            na['values'].append(nor.z())

        # Write vertex attributes
        for prim in objnode.displayNode().geometry().prims():
            nor = prim.normal()
            verts = prim.vertices()
            # Turn quad into two triangles
            if len(verts) == 4:
                write_vert(verts[0].point().position(), nor)
                write_vert(verts[1].point().position(), nor)
                write_vert(verts[2].point().position(), nor)
                write_vert(verts[2].point().position(), nor)
                write_vert(verts[3].point().position(), nor)
                write_vert(verts[0].point().position(), nor)

        # Write indices
        for i in range(0, len(pa['values']) / 3):
            ia['values'].append(i)

        obj = {}
        obj['type'] = 'mesh_object'
        return obj

    def write_lamp(self, objnode, raw):
        ld = {}
        raw['lamp_datas'].append(ld)
        ld['name'] = objnode.name() + '_data'
        ld['type'] = 'point'
        ld['color'] = [0.8, 0.8, 0.8]
        ld['strength'] = 50
        ld['cast_shadow'] = True
        ld['near_plane'] = 0.1
        ld['far_plane'] = 100
        ld['shadows_bias'] = 0.0001
        ld['fov'] = 1.5708
        ld['shadowmap_cube'] = True

        obj = {}
        obj['type'] = 'lamp_object'
        return obj

    def write_camera(self, objnode, raw):
        cd = {}
        raw['lamp_datas'].append(cd)
        cd['name'] = objnode.name() + '_data'

        obj = {}
        obj['type'] = 'camera_object'
        return obj

    def armory_export(self):
        if not os.path.exists(self.fp_build() + '/compiled/Assets'):
            os.makedirs(self.fp_build() + '/compiled/Assets')

        if not os.path.exists(self.hip_path() + '/Sources'):
            os.makedirs(self.hip_path() + '/Sources')

        # Write shader data
        if not os.path.exists(self.fp_build() + '/compiled/Shaders'):
            os.makedirs(self.fp_build() + '/compiled/Shaders')

        # Start writing the scene file
        # https://github.com/armory3d/iron/blob/master/Sources/iron/data/SceneFormat.hx
        raw = {}
        raw['name'] = self.hip_name()
        raw['material_datas'] = []
        raw['camera_datas'] = []
        raw['lamp_datas'] = []
        raw['mesh_datas'] = []
        raw['objects'] = []

        # Export scene objects
        for objnode in hou.node("/obj").children():

            if 'lamp' in str(objnode.type()):
                obj = self.write_lamp(objnode, raw)
            elif 'cam' in str(objnode.type()):
                # obj = write_camera(objnode, raw)
                pass
            elif 'geo' in str(objnode.type()):
                obj = self.write_mesh(objnode, raw)
                # Assigned materials
                matnode = None
                for ref in objnode.references():
                    if type(ref) == hou.VopNode:
                        matnode = ref
                        break
                if matnode != None:
                    # pass
                    mat = self.write_material(matnode)
                    raw['material_datas'].append(mat)
                    obj['material_refs'] = [matnode.name()]

            # Append current object
            raw['objects'].append(obj)
            obj['name'] = objnode.name()
            obj['data_ref'] = objnode.name() + '_data'
            obj['transform'] = {'values': self.write_matrix(objnode.worldTransform())}

        # Create camera data
        cam = {}
        raw['camera_datas'].append(cam)
        cam['name'] = 'Camera'
        cam['near_plane'] = 0.1
        cam['far_plane'] = 100.0
        cam['fov'] = 0.935
        cam['frustum_culling'] = True
        cam['clear_color'] = [0.2, 0.2, 0.2, 1.0]

        # Create camera object
        cam = {}
        raw['objects'].append(cam)
        cam['name'] = 'Camera'
        cam['type'] = 'camera_object'
        cam['data_ref'] = 'Camera'
        # Get viewport matrix
        pane = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
        vt = pane.curViewport().viewTransform()
        cam['transform'] = {'values': self.write_matrix(vt)}
        # Attach WalkNavigation to the camera
        cam['traits'] = []
        t = {}
        cam['traits'].append(t)
        t['type'] = 'Script'
        t['class_name'] = 'armory.trait.WalkNavigation'
        raw['camera_ref'] = 'Camera'

        # Write scene .arm file
        out_path = self.fp_build() + '/compiled/Assets/' + self.hip_name() + '.arm'
        self.write_arm(out_path, raw)

        # Write Main.hx
        with open(self.hip_path() + '/Sources/Main.hx', 'w') as f:
            f.write("""
    // Auto-generated
    package ;
    class Main {
        public static inline var projectName = '""" + self.hip_name() + """';
        public static inline var projectPackage = 'arm';
        public static function main() {
            //iron.object.BoneAnimation.skinMaxBones = 8;
            iron.object.LightObject.cascadeCount = 4;
            iron.object.LightObject.cascadeSplitFactor = 0.800000011920929;
            armory.system.Starter.main(
                '""" + self.hip_name() + """',
                0,
                false,
                true,
                false,
                1920,
                1080,
                1,
                true,
                armory.renderpath.RenderPathCreator.get
            );
        }
    }

    """)

        # Write khafile.js
        with open(self.hip_path() + '/khafile.js', 'w') as f:
            f.write("""
    // Auto-generated
    let project = new Project('""" + self.hip_name() + """');
    
    project.addSources('Sources');
    project.addLibrary('""" + self.sdk_path() + """/armory');
    project.addLibrary('""" + self.sdk_path() + """/iron');
    //project.addParameter('arm.PlayerController');
    //project.addParameter("--macro keep('arm.PlayerController')");
    project.addShaders('build_""" + self.hip_name() + """/compiled/Shaders/*.glsl', { noembed: false});
    project.addAssets('build_""" + self.hip_name() + """/compiled/Assets/**', { notinlist: true });
    project.addAssets('build_""" + self.hip_name() + """/compiled/Shaders/*.arm', { notinlist: true });
    
    project.addAssets('""" + self.sdk_path() + """/armory/Assets/brdf.png', { notinlist: true });
    project.addAssets('""" + self.sdk_path() + """/armory/Assets/smaa_area.png', { notinlist: true });
    project.addAssets('""" + self.sdk_path() + """/armory/Assets/smaa_search.png', { notinlist: true });
    project.addDefine('arm_deferred');
    project.addDefine('arm_csm');
    project.addDefine('rp_hdr');
    project.addDefine('rp_renderer=Deferred');
    project.addDefine('rp_shadowmap');
    project.addDefine('rp_shadowmap_cascade=1024');
    project.addDefine('rp_shadowmap_cube=512');
    project.addDefine('rp_background=Clear');
    project.addDefine('rp_render_to_texture');
    project.addDefine('rp_antialiasing=SMAA');
    project.addDefine('rp_supersampling=1');
    project.addDefine('rp_ssgi=SSAO');
    project.addDefine('arm_audio');
    project.addDefine('arm_noembed');
    project.addDefine('arm_soundcompress');
    project.addDefine('arm_skin');
    project.addDefine('arm_particles');
    project.addDefine('arm_yaxisup');
    project.addParameter('armory.trait.WalkNavigation');
    project.addParameter("--macro keep('armory.trait.WalkNavigation')");
    
    
    resolve(project);
    """)

    def on_compiled(self):
        # Play in Krom
        # platform.system()
        # krom_location = sdk_path() + '/Krom/win32'
        krom_location = self.sdk_path() + '/Krom'
        # krom_path = sdk_path() + '/Krom/win32/Krom.exe'
        krom_path = self.sdk_path() + '/Krom/Krom'
        os.chdir(krom_location)
        cmd = [krom_path, self.fp_build() + '/krom', self.fp_build() + '/krom-resources']
        print 'command', cmd
        subprocess.Popen(cmd)

    def armory_play(self):
        self.armory_export()

        # Compile project using node Kha/make
        # platform.system()
        # node_path = self.sdk_path() + '/nodejs/node.exe'
        node_path = self.sdk_path() + '/nodejs/node-linux64'
        khamake_path = self.sdk_path() + '/Kha/make'
        os.chdir(self.hip_path())
        cmd = [node_path, khamake_path, 'krom', '--to', self.build_dir(), '-g', 'opengl']
        print 'command final', cmd
        self.run_thread(cmd, self.on_compiled)



    # Msgpack parser with typed arrays
    # Based on u-msgpack-python v2.4.1 - v at sergeev.io
    # https://github.com/vsergeev/u-msgpack-python
    #
    # Permission is hereby granted, free of charge, to any person obtaining a copy
    # of this software and associated documentation files (the "Software"), to deal
    # in the Software without restriction, including without limitation the rights
    # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    # copies of the Software, and to permit persons to whom the Software is
    # furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in
    # all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    # THE SOFTWARE.
    #
    import struct
    import io

    def _pack_integer(self, obj, fp):
        if obj < 0:
            if obj >= -32:
                fp.write(struct.pack("b", obj))
            elif obj >= -2 ** (8 - 1):
                fp.write(b"\xd0" + struct.pack("b", obj))
            elif obj >= -2 ** (16 - 1):
                fp.write(b"\xd1" + struct.pack(">h", obj))
            elif obj >= -2 ** (32 - 1):
                fp.write(b"\xd2" + struct.pack(">i", obj))
            elif obj >= -2 ** (64 - 1):
                fp.write(b"\xd3" + struct.pack(">q", obj))
            else:
                raise Exception("huge signed int")
        else:
            if obj <= 127:
                fp.write(struct.pack("B", obj))
            elif obj <= 2 ** 8 - 1:
                fp.write(b"\xcc" + struct.pack("B", obj))
            elif obj <= 2 ** 16 - 1:
                fp.write(b"\xcd" + struct.pack(">H", obj))
            elif obj <= 2 ** 32 - 1:
                fp.write(b"\xce" + struct.pack(">I", obj))
            elif obj <= 2 ** 64 - 1:
                fp.write(b"\xcf" + struct.pack(">Q", obj))
            else:
                raise Exception("huge unsigned int")

    def _pack_nil(self, obj, fp):
        fp.write(b"\xc0")

    def _pack_boolean(self, obj, fp):
        fp.write(b"\xc3" if obj else b"\xc2")

    def _pack_float(self, obj, fp):
        # NOTE: forced 32-bit floats for Armory
        # fp.write(b"\xcb" + struct.pack(">d", obj)) # Double
        fp.write(b"\xca" + struct.pack(">f", obj))

    def _pack_string(self, obj, fp):
        obj = obj.encode('utf-8')
        if len(obj) <= 31:
            fp.write(struct.pack("B", 0xa0 | len(obj)) + obj)
        elif len(obj) <= 2 ** 8 - 1:
            fp.write(b"\xd9" + struct.pack("B", len(obj)) + obj)
        elif len(obj) <= 2 ** 16 - 1:
            fp.write(b"\xda" + struct.pack(">H", len(obj)) + obj)
        elif len(obj) <= 2 ** 32 - 1:
            fp.write(b"\xdb" + struct.pack(">I", len(obj)) + obj)
        else:
            raise Exception("huge string")

    def _pack_binary(self, obj, fp):
        if len(obj) <= 2 ** 8 - 1:
            fp.write(b"\xc4" + struct.pack("B", len(obj)) + obj)
        elif len(obj) <= 2 ** 16 - 1:
            fp.write(b"\xc5" + struct.pack(">H", len(obj)) + obj)
        elif len(obj) <= 2 ** 32 - 1:
            fp.write(b"\xc6" + struct.pack(">I", len(obj)) + obj)
        else:
            raise Exception("huge binary string")

    def _pack_array(self, obj, fp):
        if len(obj) <= 15:
            fp.write(struct.pack("B", 0x90 | len(obj)))
        elif len(obj) <= 2 ** 16 - 1:
            fp.write(b"\xdc" + struct.pack(">H", len(obj)))
        elif len(obj) <= 2 ** 32 - 1:
            fp.write(b"\xdd" + struct.pack(">I", len(obj)))
        else:
            raise Exception("huge array")

        # Float32
        if len(obj) > 0 and isinstance(obj[0], float):
            fp.write(b"\xca")
            for e in obj:
                fp.write(struct.pack(">f", e))
        # Int32
        elif len(obj) > 0 and isinstance(obj[0], int):
            fp.write(b"\xd2")
            for e in obj:
                fp.write(struct.pack(">i", e))
        # Regular
        else:
            for e in obj:
                self.pack(e, fp)

    def _pack_map(self, obj, fp):
        if len(obj) <= 15:
            fp.write(struct.pack("B", 0x80 | len(obj)))
        elif len(obj) <= 2 ** 16 - 1:
            fp.write(b"\xde" + struct.pack(">H", len(obj)))
        elif len(obj) <= 2 ** 32 - 1:
            fp.write(b"\xdf" + struct.pack(">I", len(obj)))
        else:
            raise Exception("huge array")

        for k, v in obj.items():
            self.pack(k, fp)
            self.pack(v, fp)

    def pack(self, obj, fp):
        if obj is None:
            self._pack_nil(obj, fp)
        elif isinstance(obj, bool):
            self._pack_boolean(obj, fp)
        elif isinstance(obj, int):
            self._pack_integer(obj, fp)
        elif isinstance(obj, float):
            self._pack_float(obj, fp)
        elif isinstance(obj, str):
            self._pack_string(obj, fp)
        elif isinstance(obj, bytes):
            self._pack_binary(obj, fp)
        elif isinstance(obj, list) or isinstance(obj, tuple):
            self._pack_array(obj, fp)
        elif isinstance(obj, dict):
            self._pack_map(obj, fp)
        else:
            raise Exception("unsupported type: %s" % str(type(obj)))

    def packb(self, obj):
        fp = io.BytesIO()
        self.pack(obj, fp)
        return fp.getvalue()

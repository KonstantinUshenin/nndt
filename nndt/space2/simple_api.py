import fnmatch
import os
import warnings
from typing import Optional, Sequence

import jax
from anytree.exporter import DictExporter, JsonExporter
from anytree.importer import DictImporter, JsonImporter

from nndt.math_core import train_test_split
from nndt.space2 import AbstractTreeElement, AbstractBBoxNode
from nndt.space2.group import Group
from nndt.space2.loader import FileSource
from nndt.space2.object3D import Object3D
from nndt.space2.space import Space


def _attribute_filter(attrs):
    ret = [(k, v) for k, v in attrs if isinstance(v, (int, float, str, tuple))]
    return sorted(ret)


def _children_filter(children):
    ret = [v for v in children if isinstance(v, AbstractBBoxNode)]
    return ret


def _nodecls_function(parent=None, **attrs):
    if '_nodetype' not in attrs:
        raise ValueError('_nodetype is not located in some node of space file')

    if attrs['_nodetype'] == 'FS':
        ret = DICT_NODETYPE_CLASS[attrs['_nodetype']](attrs['name'], attrs['filepath'], attrs['loader_type'],
                                                      parent=parent)
    else:
        ret = DICT_NODETYPE_CLASS[attrs['_nodetype']](attrs['name'], parent=parent)

    return ret


def load_txt(fullpath):
    return load_only_one_file(fullpath, loader_type="txt")


def load_sdt(fullpath):
    return load_only_one_file(fullpath, loader_type="sdt")


def load_mesh_obj(fullpath):
    return load_only_one_file(fullpath, loader_type="mesh_obj")


def load_only_one_file(fullpath, loader_type="txt"):
    if loader_type not in ['txt', 'sdt', 'mesh_obj']:
        raise ValueError("loader_type is unknown")

    space = Space("space")
    default = Object3D("default", parent=space)
    _filesource = FileSource(os.path.basename(fullpath), fullpath, loader_type,
                             parent=default)
    space.init()
    return space


def load_from_path(root_path,
                   template_txt='*.txt',
                   template_sdt='*sd[ft]*.npy',
                   template_mesh_obj='*.obj'):
    space = Space("space")

    def filename_to_loader_type(filename):
        if (template_txt is not None) and fnmatch.fnmatch(filename, template_txt):
            ret = 'txt'
        elif (template_sdt is not None) and fnmatch.fnmatch(filename, template_sdt):
            ret = 'sdt'
        elif (template_mesh_obj is not None) and fnmatch.fnmatch(filename, template_mesh_obj):
            ret = 'mesh_obj'
        else:
            warnings.warn("Some file in path is ignored")
            ret = None
        return ret

    def add_values(lst, fullpath, filename):
        if len(lst) >= 2:
            current_node_ = space
            for ind, name_ in enumerate(lst):
                child_names = [child.name for child in current_node_.children]
                if name_ in child_names:
                    current_node_ = current_node_[name_]
                else:
                    if ind < (len(lst) - 2):
                        current_node_ = Group(name_, parent=current_node_)
                    elif ind == (len(lst) - 2):
                        current_node_ = Object3D(name_, parent=current_node_)
                    elif ind == (len(lst) - 1):
                        loader_type = filename_to_loader_type(filename)
                        if loader_type is not None:
                            current_node_ = FileSource(name_, fullpath, loader_type, parent=current_node_)

    for root, dirs, files in os.walk(root_path, topdown=False):
        for fl in files:
            line = os.path.relpath(root, root_path)
            line2 = os.path.join(line, fl)
            lst = line2.split('/')
            add_values(lst, os.path.join(root, fl), fl)

    space.init()
    return space


def load_from_file_lists(name_list,
                         mesh_list: Optional[Sequence[str]] = None,
                         sdt_list: Optional[Sequence[str]] = None,
                         test_size: Optional[float] = None) -> Space:
    if mesh_list is not None:
        assert (len(name_list) == len(mesh_list))
    if sdt_list is not None:
        assert (len(name_list) == len(sdt_list))

    if test_size is None:
        space = Space("main")
        group = Group("default", parent=space)
        for ind, name in enumerate(name_list):
            object_ = Object3D(name, parent=group)
            if mesh_list is not None:
                mesh_source = FileSource(os.path.basename(mesh_list[ind]), mesh_list[ind], 'mesh_obj', parent=object_)
            if sdt_list is not None:
                sdt_source = FileSource(os.path.basename(sdt_list[ind]), sdt_list[ind], 'sdt', parent=object_)
    else:
        assert (0.0 < test_size < 1.0)
        space = Space("main")
        rng_key = jax.random.PRNGKey(42)
        index_train, index_test = train_test_split(range(len(name_list)), rng_key, test_size=test_size)

        group_train = Group("train", parent=space)
        for ind in index_train:
            name = name_list[ind]
            object_ = Object3D(name, parent=group_train)
            if mesh_list is not None:
                mesh_source = FileSource(os.path.basename(mesh_list[ind]), mesh_list[ind], 'mesh_obj', parent=object_)
            if sdt_list is not None:
                sdt_source = FileSource(os.path.basename(sdt_list[ind]), sdt_list[ind], 'sdt', parent=object_)

        group_test = Group("test", parent=space)
        for ind in index_test:
            name = name_list[ind]
            object_ = Object3D(name, parent=group_train)
            if mesh_list is not None:
                mesh_source = FileSource(os.path.basename(mesh_list[ind]), mesh_list[ind], 'mesh_obj', parent=object_)
            if sdt_list is not None:
                sdt_source = FileSource(os.path.basename(sdt_list[ind]), sdt_list[ind], 'sdt', parent=object_)

    space.init()
    return space


def read_space_from_file(filepath: str):
    if not os.path.exists(filepath):
        raise FileNotFoundError()

    dict_imp = DictImporter(nodecls=_nodecls_function)
    json_imp = JsonImporter(dictimporter=dict_imp)
    with open(filepath, 'r') as fl:
        space = json_imp.read(fl)

    space.init()
    return space


def from_json(json: str):
    dict_imp = DictImporter(nodecls=_nodecls_function)
    json_imp = JsonImporter(dictimporter=dict_imp)
    space = json_imp.import_(json)

    space.init()
    return space


def save_space_to_file(space: Space, filepath: str):
    filepath_with_ext = filepath if filepath.endswith('.space') else filepath + '.space'
    with open(filepath_with_ext, 'w', encoding='utf-8') as fl:
        fl.write(space.to_json())


def to_json(space: Space):
    dict_exp = DictExporter(attriter=_attribute_filter, childiter=_children_filter)
    json_exp = JsonExporter(dictexporter=dict_exp, indent=2)
    return json_exp.export(space)


DICT_NODETYPE_CLASS = {'UNDEFINED': AbstractTreeElement,
                       'S': Space,
                       'G': Group,
                       'O3D': Object3D,
                       'FS': FileSource,
                       }
DICT_CLASS_NODETYPE = {(v, k) for k, v in DICT_NODETYPE_CLASS.items()}
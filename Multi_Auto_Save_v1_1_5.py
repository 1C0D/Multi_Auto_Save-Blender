#
#    Copyright (c) 2017 Shane Ambler
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# made in response to BSE question -
# https://blender.stackexchange.com/q/95070/935

import tempfile
import os
import time
import datetime as dt
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
import bpy


bl_info = {
    "name": "Multi Auto Save",
    "author": "sambler, 1C0D",
    "version": (1, 1, 5),
    "blender": (2, 90, 0),
    "location": "blender",
    "description": "Automatically save multiple copies of a blend file",
    "warning": "Deletes old files - check your settings.",
    "wiki_url": "https://github.com/sambler/addonsByMe/blob/master/auto_blend_save.py",
    "tracker_url": "https://github.com/sambler/addonsByMe/issues",
    "category": "System",
}

"""
Use Auto Save as usual

Sometime a refresh in Recover autosave is needed to see last file

I changed the addon name "auto_blend_save" to be more explicit

"""


# TIME_FMT_STR is used for filename prefix so keep path friendly
# deleting old files relies on this format - CHANGE WITH CAUTION
TIME_FMT_STR = '%Y_%m_%d_%H_%M_%S'

last_saved = None


class AutoBlendSavePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    save_after_open: bpy.props.BoolProperty(name='Save on open',
                                            description='Save a copy of file after opening it',
                                            default=False)
    save_before_close: bpy.props.BoolProperty(name='Save before close',
                                              description='Save the current file before opening another file',
                                              default=True)
    save_on_interval: bpy.props.BoolProperty(name='Save at intervals',
                                             description='Save the file at timed intervals',
                                             default=True)
    save_interval: bpy.props.IntProperty(name='Time interval',
                                         description='Number of minutes between each save',
                                         default=2, min=1, max=120, soft_max=30)
    max_save_files: bpy.props.IntProperty(name='Max save files',
                                          description='Maximum number of copies to save, 0 means unlimited',
                                          default=10, min=0, max=100)
    compress_backups: bpy.props.BoolProperty(name='Compress backups',
                                             description='Save backups with compression enabled',
                                             default=False)

    def draw(self, context):

        layout = self.layout
        col = layout.column()
        row = col.row()
        row.prop(self, 'save_after_open')
        row = col.row()
        row.prop(self, 'save_before_close')
        row = col.row()
        row.prop(self, 'save_on_interval')
        if self.save_on_interval:
            row.prop(self, 'save_interval')
        row = col.row()
        paths = context.preferences.filepaths
        row.prop(paths, "temporary_directory", text="Temporary Files")
        row = col.row()
        row.prop(self, 'max_save_files')
        row = col.row()
        row.prop(self, 'compress_backups')


def prefs():
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__name__].preferences


def time_since_save():
    '''Minutes since last saved'''
    global last_saved
    if last_saved is None:
        last_saved = dt.datetime.now()
    now = dt.datetime.now()
    elapsed = now - last_saved
    return elapsed.seconds // 60  # minutes


def set_temporary_directory():
    prefs = bpy.context.preferences
    dir = prefs.filepaths.temporary_directory
    if prefs.filepaths.temporary_directory == "":
        prefs.filepaths.temporary_directory = tempfile.gettempdir()


def save_file():
    global last_saved
    last_saved = dt.datetime.now()
    p = prefs()
    dir = bpy.context.preferences.filepaths.temporary_directory
    if not dir:
        dir = tempfile.gettempdir()        

    save_dir = bpy.path.abspath(dir)

    try:
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
    except:
        print("Error creating auto save directory.")
        return

    basename = bpy.data.filepath

    basename = 'Unsaved.blend' if basename == '' else bpy.path.basename(
        basename)
    # delete old files if we want to limit the number of saves
    if p.max_save_files:
        try:
            # as we prefix saved blends with a timestamp
            # sorted puts the oldest prefix at the start of the list
            # this should be quicker than getting system timestamps for each file
            otherfiles = sorted([name for name in os.listdir(
                save_dir) if name.endswith('.blend') and name.endswith(basename)])
            if len(otherfiles) >= p.max_save_files:
                while len(otherfiles) >= p.max_save_files:
                    old_file = os.path.join(save_dir, otherfiles[0])
                    os.remove(old_file)
                    otherfiles.pop(0)
        except:
            print('Unable to remove old files.')

    # save the copy
    filename = last_saved.strftime(TIME_FMT_STR) + '_' + basename
    backup_file = os.path.join(save_dir, filename)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=backup_file, copy=True,
                                    compress=p.compress_backups)
        time.sleep(0.05)
    except:
        print('Error auto saving file.')


@persistent
def save_post_open(scn):
    if prefs().save_after_open:
        save_file()


@persistent
def save_pre_close(scn):
    # is_dirty means there are changes that haven't been saved to disk
    if bpy.data.is_dirty and prefs().save_before_close:
        save_file()


@persistent
def timed_save(scn):
    global last_saved

    if not prefs().save_on_interval:
        return
    if time_since_save() < prefs().save_interval:
        return
    if bpy.data.is_dirty:  # if time elapsed but no change reset time
        save_file()
    else:  # if no change reset time
        last_saved = dt.datetime.now()


def register():

    bpy.utils.register_class(AutoBlendSavePreferences)
    set_temporary_directory()
    bpy.app.handlers.load_pre.append(save_pre_close)
    bpy.app.handlers.load_post.append(save_post_open)
    bpy.app.handlers.depsgraph_update_post.append(timed_save)
    bpy.context.preferences.filepaths.use_auto_save_temporary_files = False


def unregister():
    bpy.app.handlers.load_pre.remove(save_pre_close)
    bpy.app.handlers.load_post.remove(save_post_open)
    bpy.app.handlers.depsgraph_update_post.remove(timed_save)
    bpy.utils.unregister_class(AutoBlendSavePreferences)
    bpy.context.preferences.filepaths.use_auto_save_temporary_files = True

from glob import glob
import os

import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from nipype.interfaces.freesurfer import SampleToSurface

from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

has_traitsui = True
try:
    from traitsui.api import View, Item, Group, CSVListEditor, TupleEditor
    from traitsui.menu import OKButton, CancelButton
except:
    has_traitsui = False

from .base import MetaWorkflow, load_config, register_workflow


desc = """
Map resting timeseries to surface correlations
==============================================

"""

mwf = MetaWorkflow()
mwf.uuid = '2b00d9ee8bde11e1a0960023dfa375f2'
mwf.tags = ['surface', 'resting', 'correlation']


def check_path(path):
    fl = glob(path)
    if not len(fl):
        print "ERROR:", path, "does NOT exist!"
    else:
        print "Exists:", fl


# create gui
class config(HasTraits):
    uuid = traits.Str(desc="UUID")

    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(exists=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(mandatory=True, desc="Freesurfer subjects directory")

    # Execution
    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor",
                         usedefault=True,
                         desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
                                                      usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
                     desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    # Subjects
    subjects = traits.List(traits.Str, mandatory=True, usedefault=True,
                          desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    func_template = traits.String('%s/cleaned_resting.nii.gz')
    reg_template = traits.String('%s/cleaned_resting_reg.dat')
    ref_template = traits.String('%s/cleaned_resting_ref.nii.gz')

    # Target surface
    target_surf = traits.Enum('fsaverage5', 'fsaverage', 'fsaverage3',
                              'fsaverage4', 'fsaverage6',
                              desc='which average surface to map to')
    surface_fwhm = traits.List([5], traits.Float(), mandatory=True,
                               usedefault=True,
                               desc="How much to smooth on target surface")
    projection_stem = traits.Str('-projfrac-avg 0 1 0.1',
                                 desc='how to project data onto the surface')

    # Atlas mapping
    #surface_atlas = ??

    # Buttons
    check_func_datagrabber = Button("Check")

    def _check_func_datagrabber_fired(self):
        subs = self.subjects
        for s in subs:
            for template in [self.func_template, self.ref_template,
                             self.reg_template]:
                check_path(os.path.join(self.base_dir, template % s))
            check_path(os.path.join(self.surf_dir, s))

def create_config():
    c = config()
    c.uuid = mwf.uuid
    return c

mwf.config_ui = create_config
mwf.help = desc


def create_view():
    view = View(Group(Item(name='working_dir'),
                      Item(name='sink_dir'),
                      Item(name='crash_dir'),
                      Item(name='surf_dir'),
                      label='Directories', show_border=True),
                Group(Item(name='run_using_plugin'),
                      Item(name='plugin', enabled_when="run_using_plugin"),
                      Item(name='plugin_args', enabled_when="run_using_plugin"),
                      Item(name='test_mode'),
                      label='Execution Options', show_border=True),
                Group(Item(name='subjects', editor=CSVListEditor()),
                      Item(name='base_dir', ),
                      Item(name='func_template'),
                      Item(name='reg_template'),
                      Item(name='ref_template'),
                      Item(name='check_func_datagrabber'),
                      label='Subjects', show_border=True),
                Group(Item(name='target_surf'),
                      Item(name='surface_fwhm', editor=CSVListEditor()),
                      Item(name='projection_stem'),
                      label='Smoothing', show_border=True),
                buttons=[OKButton, CancelButton],
                resizable=True,
                width=1050)
    return view

mwf.config_view = create_view


def create_correlation_matrix(infile):
    import os
    import numpy as np
    import scipy.io as sio
    import nibabel as nb
    from nipype.utils.filemanip import split_filename
    _, name, _ = split_filename(infile)
    matfile = os.path.abspath(name + '.mat')
    img = nb.load(infile)
    corrmat = np.corrcoef(np.squeeze(img.get_data()))
    sio.savemat(matfile, {'corrmat': corrmat})
    return matfile


def create_workflow(c):
    workflow = pe.Workflow(name='surface_correlation')
    inputnode = pe.Node(util.IdentityInterface(fields=['subject_id']),
                        name='subjectsource')
    inputnode.iterables = ('subject_id', c.subjects)
    datasource = pe.Node(nio.DataGrabber(infields=['subject_id'],
                                         outfields=['timeseries_file',
                                                   'ref_file',
                                                   'reg_file']),
                         name='datasource')
    datasource.inputs.template = '*'
    datasource.inputs.base_directory = os.path.abspath(c.base_dir)
    datasource.inputs.field_template = dict(timeseries_file=c.func_template,
                                            ref_file=c.ref_template,
                                            reg_file=c.reg_template)
    workflow.connect(inputnode, 'subject_id', datasource, 'subject_id')

    # vol2surf
    vol2surf = pe.Node(SampleToSurface(),
                       name='sampletimeseries')
    vol2surf.inputs.projection_stem = c.projection_stem
    vol2surf.iterables = [('hemi', ['lh', 'rh']),
                          ('smooth_surf', c.surface_fwhm)]
    vol2surf.inputs.interp_method = 'trilinear'
    vol2surf.inputs.out_type = 'niigz'
    vol2surf.inputs.target_subject = c.target_surf
    vol2surf.inputs.subjects_dir = c.surf_dir

    workflow.connect(datasource, 'timeseries_file', vol2surf, 'source_file')
    workflow.connect(datasource, 'reg_file', vol2surf, 'reg_file')
    workflow.connect(datasource, 'ref_file', vol2surf, 'reference_file')

    # create correlation matrix
    corrmat = pe.Node(util.Function(input_names=['infile'],
                                    output_names=['corrmatfile'],
                                    function=create_correlation_matrix),
                      name='correlation_matrix')
    corrmat.overwrite = True
    workflow.connect(vol2surf, 'out_file', corrmat, 'infile')

    datasink = pe.Node(nio.DataSink(), name='sinker')
    datasink.inputs.base_directory = c.sink_dir
    datasink.inputs.regexp_substitutions = [('_subject_id.*smooth_surf', 'surffwhm')]
    workflow.connect(inputnode, 'subject_id', datasink, 'container')
    workflow.connect(corrmat, 'corrmatfile', datasink, '@corrmat')
    return workflow


def main(config_file):
    c = load_config(config_file, create_config)
    workflow = create_workflow(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir}}
    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main
register_workflow(mwf)
from .base import MetaWorkflow, load_json, register_workflow
import traits.api as traits
from traitsui.api import View, Item, Group
from traitsui.menu import OKButton, CancelButton
import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import os
import nipype.interfaces.io as nio

mwf = MetaWorkflow()
mwf.help = """
Resting State preprocessing workflow
====================================

"""

mwf.uuid = '7757e3168af611e1b9d5001e4fb1404c'
mwf.tags = ['resting-state','fMRI','preprocessing','fsl','freesurfer','nipy']
mwf.script_dir = 'u0a14c5b5899911e1bca80023dfa375f2'

# create_gui
from workflow1 import config_ui, get_dataflow

r_config = config_ui
r_config.add_class_trait("highpass_freq", traits.Float())
r_config.add_class_trait("lowpass_freq", traits.Float())
r_config.add_class_trait("reg_params", traits.List(traits.Bool()))

# create_workflow

from scripts.u0a14c5b5899911e1bca80023dfa375f2.base import create_rest_prep
from scripts.u0a14c5b5899911e1bca80023dfa375f2.utils import get_datasink, get_substitutions, get_regexp_substitutions

def prep_workflow(c, fieldmap):

    if fieldmap:
        modelflow = pe.Workflow(name='preprocfm')
    else:
        modelflow = pe.Workflow(name='preproc')


    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', c["subjects"].split(','))

    # generate datagrabber
    
    dataflow = get_dataflow(c)
    
    modelflow.connect(infosource, 'subject_id',
                      dataflow, 'subject_id')
    
    # generate preprocessing workflow
    preproc = create_rest_prep(fieldmap=fieldmap)
    
    # make a data sink
    sinkd = get_datasink(c["sink_dir"], c["fwhm"])
    
    if fieldmap:
        datasource_fieldmap = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                                   outfields=['mag','phase']),
                         name = "fieldmap_datagrabber")
        datasource_fieldmap.inputs.base_directory = c["field_dir"]
        datasource_fieldmap.inputs.template ='*'
        datasource_fieldmap.inputs.field_template = dict(mag=c["magnitude_template"],
                                                phase=c["phase_template"])
        datasource_fieldmap.inputs.template_args = dict(mag=[['subject_id']],
                                               phase=[['subject_id']])
                                               
        preproc.inputs.inputspec.FM_Echo_spacing = c["echospacing"]
        preproc.inputs.inputspec.FM_TEdiff = c["TE_diff"]
        preproc.inputs.inputspec.FM_sigma = c["sigma"]
        modelflow.connect(infosource, 'subject_id',
                          datasource_fieldmap, 'subject_id')
        modelflow.connect(datasource_fieldmap,'mag',
                          preproc,'fieldmap_input.magnitude_file')
        modelflow.connect(datasource_fieldmap,'phase',
                          preproc,'fieldmap_input.phase_file')
        modelflow.connect(preproc, 'outputspec.vsm_file',
                          sinkd, 'preproc.fieldmap')
        modelflow.connect(preproc, 'outputspec.FM_unwarped_mean',
                          sinkd, 'preproc.mean')
    else:
        modelflow.connect(preproc, 'outputspec.mean',
                          sinkd, 'preproc.mean')

    # inputs
    preproc.inputs.fwhm_input.fwhm = c["fwhm"]
    preproc.inputs.inputspec.num_noise_components = c["num_noise_components"]
    preproc.crash_dir = c["crash_dir"]
    modelflow.connect(infosource, 'subject_id', preproc, 'inputspec.fssubject_id')
    preproc.inputs.inputspec.fssubject_dir = c["surf_dir"]
    preproc.get_node('fwhm_input').iterables = ('fwhm',c["fwhm"])
    preproc.inputs.inputspec.ad_normthresh = c["norm_thresh"]
    preproc.inputs.inputspec.ad_zthresh = c["z_thresh"]
    preproc.inputs.inputspec.tr = c["TR"]
    preproc.inputs.inputspec.interleaved = c["Interleaved"]
    preproc.inputs.inputspec.sliceorder = c["SliceOrder"]
    preproc.inputs.inputspec.compcor_select = c["compcor_select"]
    preproc.inputs.inputspec.highpass_sigma = 1/(2*c["TR"]*c["highpass_freq"])
    preproc.inputs.inputspec.lowpass_sigma = 1/(2*c["TR"]*c["lowpass_freq"])
    preproc.inputs.inputspec.reg_params = c["reg_params"]

    
    modelflow.connect(infosource, 'subject_id', sinkd, 'container')
    modelflow.connect(infosource, ('subject_id', get_substitutions, fieldmap),
                      sinkd, 'substitutions')
    modelflow.connect(infosource, ('subject_id', get_regexp_substitutions,
                                   fieldmap),
                      sinkd, 'regexp_substitutions')

    # make connections

    modelflow.connect(dataflow,'func',
                      preproc,'inputspec.func')
    modelflow.connect(preproc, 'outputspec.motion_parameters',
                      sinkd, 'preproc.motion')
    modelflow.connect(preproc, 'plot_motion.out_file',
                      sinkd, 'preproc.motion.@plots')
    modelflow.connect(preproc, 'outputspec.mask',
                      sinkd, 'preproc.mask')
    modelflow.connect(preproc, 'outputspec.outlier_files',
                      sinkd, 'preproc.art')
    modelflow.connect(preproc, 'outputspec.outlier_stat_files',
                      sinkd, 'preproc.art.@stats')
    modelflow.connect(preproc, 'outputspec.combined_motion',
                      sinkd, 'preproc.art.@norm')
    modelflow.connect(preproc, 'outputspec.reg_file',
                      sinkd, 'preproc.bbreg')
    modelflow.connect(preproc, 'outputspec.reg_fsl_file',
                      sinkd, 'preproc.bbreg.@fsl')
    modelflow.connect(preproc, 'outputspec.reg_cost',
                      sinkd, 'preproc.bbreg.@reg_cost')
    modelflow.connect(preproc, 'outputspec.highpassed_files',
                      sinkd, 'preproc.highpass')
    modelflow.connect(preproc, 'outputspec.tsnr_file',
                      sinkd, 'preproc.tsnr')
    modelflow.connect(preproc, 'outputspec.stddev_file',
                      sinkd, 'preproc.tsnr.@stddev')
    modelflow.connect(preproc, 'outputspec.filter_file',
                      sinkd, 'preproc.regressors')
    modelflow.connect(preproc, 'outputspec.z_img', 
                      sinkd, 'preproc.output.@zscored')
    modelflow.connect(preproc, 'outputspec.scaled_files',
                      sinkd, 'preproc.output.@fullspectrum')
    modelflow.connect(preproc, 'outputspec.bandpassed_file',
                      sinkd, 'preproc.output.@bandpassed')

    modelflow.base_dir = os.path.join(c["working_dir"],'work_dir')
    return modelflow
    
def main(config_file):
    c = load_json(config_file)
    preprocess = prep_workflow(c, c["use_fieldmap"])
    realign = preprocess.get_node('preproc.realign')
    #realign.inputs.loops = 2
    realign.inputs.speedup = 10
    realign.plugin_args = c["plugin_args"]
    preprocess.config = {'execution' : {'crashdump_dir' : c["crash_dir"]}}
    
    if len(c["subjects"].split(',')) == 1:
        preprocess.write_graph(graph2use='exec',
                               dotfilename='single_subject_exec.dot')
    if c["run_on_grid"]:
        preprocess.run(plugin=c["plugin"], plugin_args = c["plugin_args"])
    else:
        preprocess.run()
        
mwf.workflow_main_function = main
mwf.config_ui = lambda : r_config

view = View(Group(Item(name='working_dir'),
             Item(name='sink_dir'),
             Item(name='crash_dir'),
             Item(name='json_sink'),
             Item(name='surf_dir'),
             label='Directories',show_border=True),
             Group(Item(name='run_on_grid'),
             Item(name='plugin',enabled_when="run_on_grid"),
             Item(name='plugin_args',enabled_when="run_on_grid"),
             Item(name='test_mode'),
             label='Execution Options',show_border=True),
             Group(Item(name='subjects'),
             Item(name='base_dir'),
             Item(name='func_template'),
             Item(name='check_func_datagrabber'),
             label='Subjects',show_border=True),
             Group(Item(name='use_fieldmap'),
             Item(name='field_dir',enabled_when="use_fieldmap"),
             Item(name='magnitude_template',enabled_when="use_fieldmap"),
             Item(name='phase_template',enabled_when="use_fieldmap"),
             Item(name='check_field_datagrabber',enabled_when="use_fieldmap"),
             Item(name='echospacing',enabled_when="use_fieldmap"),
             Item(name='TE_diff',enabled_when="use_fieldmap"),
             Item(name='sigma',enabled_when="use_fieldmap"),
             label='Fieldmap',show_border=True),
             Group(Item(name='TR'),
             Item(name='Interleaved'),
             Item(name='SliceOrder'),
             label='Motion Correction',show_border=True),
             Group(Item(name='norm_thresh'),
             Item(name='z_thresh'),
             label='Artifact Detection',show_border=True),
             Group(Item(name='compcor_select'),
             Item(name='num_noise_components'),
             label='CompCor',show_border=True),
             Group(Item(name='reg_params'),
             label='Filtering',show_border=True),
             Group(Item(name='fwhm'),
             label='Smoothing',show_border=True),
             Group(Item(name='highpass_freq'),
             Item(name='lowpass_freq'),
             label='Bandpass Filter',show_border=True),
             buttons = [OKButton, CancelButton],
             resizable=True,
             width=1050)
             
mwf.config_view = view
register_workflow(mwf)
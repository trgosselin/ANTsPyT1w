import sys, os
import unittest

os.environ["TF_NUM_INTEROP_THREADS"] = "8"
os.environ["TF_NUM_INTRAOP_THREADS"] = "8"
os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = "8"

import antspyt1w
import antspynet
import ants

testingClass = unittest.TestCase( )

##### get example data + reference templates
fn = antspyt1w.get_data('PPMI-3803-20120814-MRI_T1-I340756', target_extension='.nii.gz' )
tfn = antspyt1w.get_data('T_template0', target_extension='.nii.gz' )
tfnw = antspyt1w.get_data('T_template0_WMP', target_extension='.nii.gz' )
tlrfn = antspyt1w.get_data('T_template0_LR', target_extension='.nii.gz' )
bfn = antspynet.get_antsxnet_data( "croppedMni152" )

##### read images and do simple bxt ops
templatea = ants.image_read( tfn )
templatea = ( templatea * antspynet.brain_extraction( templatea, 't1' ) ).iMath( "Normalize" )
templateawmprior = ants.image_read( tfnw )
templatealr = ants.image_read( tlrfn )
templateb = ants.image_read( bfn )
templateb = ( templateb * antspynet.brain_extraction( templateb, 't1' ) ).iMath( "Normalize" )
img = ants.image_read( fn )
imgbxt = antspyt1w.brain_extraction( img )
img = img * imgbxt

# this is an unbiased method for identifying predictors that can be used to
# rank / sort data into clusters, some of which may be associated
# with outlierness or low-quality data
templatesmall = ants.resample_image( templateb, (91,109,91), use_voxels=True )
rbp = antspyt1w.random_basis_projection( img, templatesmall, 10 )
testingClass.assertAlmostEqual(
    float( rbp['RandBasisProj01'] ),
    float( -0.3695626974439423 ), 5, "RBP result not close enough")

# assuming data is reasonable quality, we should proceed with the rest ...
mylr = antspyt1w.label_hemispheres( img, templatea, templatealr )

# optional - quick look at result
# ants.plot(img,axis=2,ncol=8,nslices=24, filename="/tmp/temp.png" )
##### intensity modifications
img = ants.iMath( img, "Normalize" )
img = ants.denoise_image( img, imgbxt, noise_model='Rician')
img = ants.n4_bias_field_correction( img ).iMath("Normalize")
testingClass.assertAlmostEqual(
    float( img.mean() ),
    float( 0.07115734368562698 ), 5, "img mean after n4 result not close enough")

##### hierarchical labeling
myparc = antspyt1w.deep_brain_parcellation( img, templateb,
    do_cortical_propagation=True, verbose=True )

##### accumulate data into data frames
hemi = antspyt1w.map_segmentation_to_dataframe( "hemisphere", myparc['hemisphere_labels'] )
tissue = antspyt1w.map_segmentation_to_dataframe( "tissues", myparc['tissue_segmentation'] )
dktl = antspyt1w.map_segmentation_to_dataframe( "lobes", myparc['dkt_lobes'] )
dktp = antspyt1w.map_segmentation_to_dataframe( "dkt", myparc['dkt_parcellation'] )

testingClass.assertAlmostEqual(
    float( hemi['VolumeInMillimeters'][0] ),
    float( 733068.0 ), 8, "hemi volume not close enough")
testingClass.assertAlmostEqual(
    float( dktl['VolumeInMillimeters'][0] ),
    float( 186208.0 ), 8, "dktl volume not close enough")
testingClass.assertAlmostEqual(
    float( dktp['VolumeInMillimeters'][1] ),
    float( 12595.0 ), 8, "dktp volume not close enough")

##### traditional deformable registration as a high-resolution complement to above
reg = antspyt1w.hemi_reg(
    input_image = img,
    input_image_tissue_segmentation = myparc['tissue_segmentation'],
    input_image_hemisphere_segmentation = mylr,
    input_template=templatea,
    input_template_hemisphere_labels=templatealr,
    output_prefix="/tmp/SYN",
    is_test=False )

testingClass.assertAlmostEqual(
    float( reg['rhjac'].max() ),
    float( 1.1146247386932373 ), 2, "rhjac max not close enough")

##### how to use the hemi-reg output to generate any roi value from a template roi
wm_tracts = ants.image_read( antspyt1w.get_data( "wm_major_tracts", target_extension='.nii.gz' ) )
wm_tractsL = ants.apply_transforms( img, wm_tracts, reg['synL']['invtransforms'],
  interpolator='genericLabel' ) * ants.threshold_image( mylr, 1, 1  )
wm_tractsR = ants.apply_transforms( img, wm_tracts, reg['synR']['invtransforms'],
  interpolator='genericLabel' ) * ants.threshold_image( mylr, 2, 2  )
wmtdfL = antspyt1w.map_segmentation_to_dataframe( "wm_major_tracts", wm_tractsL )
wmtdfR = antspyt1w.map_segmentation_to_dataframe( "wm_major_tracts", wm_tractsR )

testingClass.assertAlmostEqual(
    float( wmtdfL['VolumeInMillimeters'][1]/10000 ),
    float( 19572.0/10000 ), 2, "wmtdfL volume not close enough")

##### specialized labeling for hippocampus
hippLR = antspyt1w.deep_hippo( img, templateb )
testingClass.assertAlmostEqual(
    float( hippLR['HLStats']['VolumeInMillimeters'][0]/20000.0 ),
    float( 2822.00/20000.0 ), 2, "HLStats volume not close enough")

##### below here are more exploratory nice to have outputs
myhypo = antspyt1w.t1_hypointensity( img,
  myparc['tissue_probabilities'][3], # wm posteriors
  templatea,
  templateawmprior )

testingClass.assertAlmostEqual(
    float( myhypo['wmh_summary']['Value'][1]  * 0.0001 ),
    float( 12318.5093207285 * 0.0001), 2, "wmh_summary integral not close enough")

##### specialized labeling for hypothalamus
# FIXME hypothalamus
sys.exit(os.EX_OK) # code 0, all ok
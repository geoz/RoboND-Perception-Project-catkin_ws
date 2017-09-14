import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
from pcl_helper import *


def rgb_to_hsv(rgb_list):
    rgb_normalized = [1.0*rgb_list[0]/255, 1.0*rgb_list[1]/255, 1.0*rgb_list[2]/255]
    hsv_normalized = matplotlib.colors.rgb_to_hsv([[rgb_normalized]])[0][0]
    return hsv_normalized


def compute_color_histograms(cloud, using_hsv=False):

    # Compute histograms for the clusters
    point_colors_list = []

    # Step through each point in the point cloud
    for point in pc2.read_points(cloud, skip_nans=True):
        rgb_list = float_to_rgb(point[3])
        if using_hsv:
            point_colors_list.append(rgb_to_hsv(rgb_list) * 255)
        else:
            point_colors_list.append(rgb_list)

    # Populate lists with color values
    channel_1_vals = []
    channel_2_vals = []
    channel_3_vals = []

    for color in point_colors_list:
        channel_1_vals.append(color[0])
        channel_2_vals.append(color[1])
        channel_3_vals.append(color[2])
    
    # TODO: Compute histograms
    channel_1_hist, bin_edges = np.histogram(channel_1_vals, bins=64, range=(0, 256)) 
    channel_2_hist, bin_edges = np.histogram(channel_2_vals, bins=64, range=(0, 256))
    channel_3_hist, bin_edges = np.histogram(channel_3_vals, bins=64, range=(0, 256))

    # TODO: Concatenate and normalize the histograms
    hist_features = np.concatenate((channel_1_hist, channel_2_hist, channel_3_hist)).astype(np.float64)
    norm_features = hist_features / np.sum(hist_features)

    # Generate random features for demo mode.  
    # Replace normed_features with your feature vector
    normed_features = norm_features

    return normed_features 


def compute_normal_histograms(normal_cloud):
    norm_x_vals = []
    norm_y_vals = []
    norm_z_vals = []

    for norm_component in pc2.read_points(normal_cloud,
                                          field_names = ('normal_x', 'normal_y', 'normal_z'),
                                          skip_nans=True):
        norm_x_vals.append(norm_component[0])
        norm_y_vals.append(norm_component[1])
        norm_z_vals.append(norm_component[2])

    # TODO: Compute histograms of normal values (just like with color)
    channel_1_vals = []
    channel_2_vals = []
    channel_3_vals = []

    for i in range(len(norm_x_vals)):
        channel_1_vals.append(norm_x_vals[i])
        channel_2_vals.append(norm_y_vals[i])
        channel_3_vals.append(norm_z_vals[i])

    channel_1_hist, bin_edges = np.histogram(channel_1_vals, bins=64, range=(-1.0,1.0)) 
    channel_2_hist, bin_edges = np.histogram(channel_2_vals, bins=64, range=(-1.0,1.0))
    channel_3_hist, bin_edges = np.histogram(channel_3_vals, bins=64, range=(-1.0,1.0))

    # TODO: Concatenate and normalize the histograms
    hist_features = np.concatenate((channel_1_hist, channel_2_hist, channel_3_hist)).astype(np.float64)
    norm_features = hist_features / np.sum(hist_features)

    # Generate random features for demo mode.  
    # Replace normed_features with your feature vector
    normed_features = norm_features

    return normed_features

#!/usr/bin/env python

# Import modules
import numpy as np
import sklearn
from sklearn.preprocessing import LabelEncoder
import pickle
from sensor_stick.srv import GetNormals
from sensor_stick.features import compute_color_histograms
from sensor_stick.features import compute_normal_histograms
from visualization_msgs.msg import Marker
from sensor_stick.marker_tools import *
from sensor_stick.msg import DetectedObjectsArray
from sensor_stick.msg import DetectedObject
from sensor_stick.pcl_helper import *

import rospy
import tf
from geometry_msgs.msg import Pose
from std_msgs.msg import Float64
from std_msgs.msg import Int32
from std_msgs.msg import String
from pr2_robot.srv import *
from rospy_message_converter import message_converter
import yaml


# Helper function to get surface normals
def get_normals(cloud):
    get_normals_prox = rospy.ServiceProxy('/feature_extractor/get_normals', GetNormals)
    return get_normals_prox(cloud).cluster

# Helper function to create a yaml friendly dictionary from ROS messages
def make_yaml_dict(test_scene_num, arm_name, object_name, pick_pose, place_pose):
    yaml_dict = {}
    yaml_dict["test_scene_num"] = test_scene_num.data
    yaml_dict["arm_name"]  = arm_name.data
    yaml_dict["object_name"] = object_name.data
    yaml_dict["pick_pose"] = message_converter.convert_ros_message_to_dictionary(pick_pose)
    yaml_dict["place_pose"] = message_converter.convert_ros_message_to_dictionary(place_pose)
    return yaml_dict

# Helper function to output to yaml file
def send_to_yaml(yaml_filename, dict_list):
    data_dict = {"object_list": dict_list}
    with open(yaml_filename, 'w') as outfile:
        yaml.dump(data_dict, outfile, default_flow_style=False)

# Callback function for your Point Cloud Subscriber
def pcl_callback(pcl_msg):

# Exercise-2 TODOs:

    # Convert ROS msg to PCL data
    cloud = ros_to_pcl(pcl_msg)
    
    # Statistical Outlier Filtering
    cloud_outlier_filter = cloud.make_statistical_outlier_filter()
    cloud_outlier_filter.set_mean_k(50) # TODO: try other values
    cloud_outlier_filter.set_std_dev_mul_thresh(1.0)
    filtered_cloud = cloud_outlier_filter.filter()


    # Voxel Grid Downsampling
    # Decrease resolution for faster calculations, but it should still do 
    # a good job of representing the point cloud as a whole.
    # Create a VoxelGrid filter object for our input point cloud
    vox = filtered_cloud.make_voxel_grid_filter()
    # Choose a voxel (also known as leaf) size
    # Note: this (1) is a poor choice of leaf size   
    # Experiment and find the appropriate size!
    LEAF_SIZE = 0.005  # TODO: Try 0.001 or 0.005, ( 0.01 doesnt work)
    vox.set_leaf_size(LEAF_SIZE, LEAF_SIZE, LEAF_SIZE)
    # Call the filter function to obtain the resultant downsampled point cloud
    cloud_voxel = vox.filter()

    # PassThrough Filter vertical
    # If you have some prior information about the location of your target
    # in the scene,you can apply a Pass Through Filter to remove useless data
    # from your point cloud.
    # The Pass Through Filter works much like a cropping tool, which allows you 
    # to crop any given 3D point cloud by specifying an axis with 
    # cut-off values along that axis.
    # Create a PassThrough filter object:
    passthrough = cloud_voxel.make_passthrough_filter()
    filter_axis = 'z'
    passthrough.set_filter_field_name(filter_axis)
    axis_min = 0.6 # TODO: try different values 0.7
    axis_max = 1.4 # 1.1
    passthrough.set_filter_limits(axis_min, axis_max)
    cloud_passthrough = passthrough.filter()

    # PassThrough Filter horizontal
    # It is needed cause we get objects that dont excist
    passthrough = cloud_passthrough.make_passthrough_filter()
    filter_axis = 'y'
    passthrough.set_filter_field_name(filter_axis)
    axis_min = -0.5 # TODO: better 0.4? No it removes part of of objects 
    axis_max = 0.5 
    passthrough.set_filter_limits(axis_min, axis_max)
    cloud_passthrough = passthrough.filter()



    # RANSAC Plane Segmentation
    # Create the segmentation object
    seg = cloud_passthrough.make_segmenter()
    # Set the model you wish to fit 
    seg.set_model_type(pcl.SACMODEL_PLANE)
    seg.set_method_type(pcl.SAC_RANSAC)
    # Max distance for a point to be considered fitting the model
    # Experiment with different values for max_distance 
    # for segmenting the table
    max_distance = 0.01
    seg.set_distance_threshold(max_distance)
    # Call the segment function to obtain set of inlier indices and model coefficients
    inliers, coefficients = seg.segment()

    # Extract inliers and outliers
    cloud_table = cloud_passthrough.extract(inliers, negative=False)
    cloud_objects = cloud_passthrough.extract(inliers, negative=True)

    # Euclidean Clustering
    # Use only spatial information:
    white_cloud = XYZRGB_to_XYZ(cloud_objects)
    tree = white_cloud.make_kdtree()
    # Create a cluster extraction object
    ec = white_cloud.make_EuclideanClusterExtraction()
    # Set tolerances for distance threshold 
    # as well as minimum and maximum cluster size (in points)
    # NOTE: These are poor choices of clustering parameters
    # Your task is to experiment and find values that work for segmenting objects.

    ec.set_ClusterTolerance(0.01) 
    ec.set_MinClusterSize(50)
    ec.set_MaxClusterSize(5000)

    # Search the k-d tree for clusters
    ec.set_SearchMethod(tree)
    # Extract indices for each of the discovered clusters
    cluster_indices = ec.Extract()

    # Create Cluster-Mask Point Cloud to visualize each cluster separately
    cluster_color = get_color_list(len(cluster_indices))
    color_cluster_point_list = []  

    for j, indices in enumerate(cluster_indices):
        for i, indice in enumerate(indices):
            color_cluster_point_list.append([white_cloud[indice][0],
                                             white_cloud[indice][1],
                                             white_cloud[indice][2],
                                             rgb_to_float(cluster_color[j])])
 
    # Create new cloud containing all clusters, each with unique color
    cluster_cloud = pcl.PointCloud_PointXYZRGB()
    cluster_cloud.from_list(color_cluster_point_list)

    # Convert PCL data to ROS messages
    ros_msg_table = pcl_to_ros(cloud_table)
    ros_msg_objects = pcl_to_ros(cloud_objects)
    ros_cluster_cloud = pcl_to_ros(cluster_cloud)

    # Publish ROS messages
    pcl_objects_pub.publish(ros_msg_objects)
    pcl_table_pub.publish(ros_msg_table)
    pcl_cluster_pub.publish(ros_cluster_cloud)

# Exercise-3 TODOs:

    # Create empty lists for object recognition
    # Classify the clusters!
    detected_objects_labels = []
    detected_objects = []

    # Classify the clusters! (loop through each detected cluster one at a time)

    # Cycle through each of the segmented clusters for object recognition
    for index, pts_list in enumerate(cluster_indices):
        # Grab the points for the cluster from the extracted outliers (cloud_objects)
        pcl_cluster = cloud_objects.extract(pts_list)
        # Convert the cluster from pcl to ROS using helper function
        ros_cluster = pcl_to_ros(pcl_cluster)

        # Extract histogram features
        chists = compute_color_histograms(ros_cluster, using_hsv=True)
        
	# TODO: RGB
        #chists_rgb = compute_color_histograms(ros_cluster, using_hsv=False)

        normals = get_normals(ros_cluster)
        nhists = compute_normal_histograms(normals)
        feature = np.concatenate((chists, nhists))
        
	# TODO: RGB
        #feature = np.concatenate((feature, chists_rgb))
        # Make the prediction, retrieve the label for the result
        # and add it to detected_objects_labels list

        prediction = clf.predict(scaler.transform(feature.reshape(1,-1)))
        label = encoder.inverse_transform(prediction)[0]
        detected_objects_labels.append(label)

        # Publish a label into RViz
        label_pos = list(white_cloud[pts_list[0]])
        label_pos[2] += .4
        object_markers_pub.publish(make_label(label,label_pos, index))

        # Add the detected object to the list of detected objects.
        do = DetectedObject()
        do.label = label
        do.cloud = ros_cluster
        detected_objects.append(do)    

    rospy.loginfo('Detected {} objects: {}'.format(len(detected_objects_labels), detected_objects_labels))

    # Publish the list of detected objects
    # This is the output you'll need to complete the upcoming project!
    detected_objects_pub.publish(detected_objects)


    # Suggested location for where to invoke your pr2_mover() function within pcl_callback()
    # Could add some logic to determine whether or not your object detections are robust
    # before calling pr2_mover()

    try:
        pr2_mover(detected_objects)
    except rospy.ROSInterruptException:
        pass





# function to load parameters and request PickPlace service
def pr2_mover(object_list):

    # Initialize variables
    dict_list = [] # for yaml fifles
    centroids = [] # to be list of tuples (x, y, z)
    place_dict = {} # for dropboxes


    # Get/Read parameters
    # Retreive the 'pick' list from the parameter server
    pick_list_param = rospy.get_param('/object_list')
    # Retreive the 'place' list
    place_list_param = rospy.get_param('/dropbox')


    # Parse parameters into individual variables
    for box in place_list_param:
        place_dict[ box['name'] ] = box['position']
    

    # TODO: Rotate PR2 in place to capture side tables for the collision map

    
    # Loop through the pick list
    for pick_obj in pick_list_param:
    
        # Read pick object name:
        object_name = String()
        object_name.data = pick_obj['name']

        print("Pick item:")
        print(object_name.data)


        # Initialize pose
        pick_pose = Pose()
        pick_pose.position.x = 0
        pick_pose.position.y = 0
        pick_pose.position.z = 0
        pick_pose.orientation.x = 0
        pick_pose.orientation.y = 0
        pick_pose.orientation.z = 0
        pick_pose.orientation.w = 0


        # Get the PointCloud for a given object and obtain it's centroid
        for classified_obj in object_list:

            # if an object in the pick list was identified
            if classified_obj.label == object_name.data:

                print("Found item:")
                print(object_name.data)

                # Create 'pick_pose' for the object
                points_arr = ros_to_pcl(classified_obj.cloud).to_array()
                pick_pose_centroid = np.mean(points_arr, axis=0)[:3]
                
                pick_pose.position.x = np.asscalar(pick_pose_centroid[0])
                pick_pose.position.y = np.asscalar(pick_pose_centroid[1])
                pick_pose.position.z = np.asscalar(pick_pose_centroid[2])

                break

        # Assign the arm to be used for pick_place
        arm_name = String()
        if pick_obj['group'] == 'green':
            arm_name.data = 'right'
        else:
            arm_name.data = 'left'


        # Create place pose for object
        place_pose = Pose()
        place_pose.position.x = place_dict[arm_name.data][0]
        place_pose.position.y = place_dict[arm_name.data][1]
        place_pose.position.z = place_dict[arm_name.data][2]
        place_pose.orientation.x = 0
        place_pose.orientation.y = 0
        place_pose.orientation.z = 0
        place_pose.orientation.w = 0
       
   
        # TODO: Change these depending on the world chosen
        test_scene_num = Int32()
        test_scene_num.data = 3

        # Create a list of dictionaries (made with make_yaml_dict()) for later output to yaml format
        yaml_dict = make_yaml_dict(test_scene_num, arm_name, object_name, pick_pose, place_pose)
        dict_list.append(yaml_dict)

        # Output your request parameters into output yaml file


        # Wait for 'pick_place_routine' service to come up
        rospy.wait_for_service('pick_place_routine')

        # It is not needed for yaml creation
        #try:
        #    pick_place_routine = rospy.ServiceProxy('pick_place_routine', PickPlace)

            # TODO: Insert your message variables to be sent as a service request
        #    resp = pick_place_routine(test_scene_num, object_name, arm_name, pick_pose, place_pose)

        #    print ("Response: ",resp.success)

        #except rospy.ServiceException, e:
        #    print "Service call failed: %s"%e
    
    print(dict_list)


    yaml_filename = "output_" + str(test_scene_num.data) + ".yaml"
    send_to_yaml(yaml_filename, dict_list)
    print("Yaml file created")



if __name__ == '__main__':

    # ROS node initialization
    rospy.init_node('object_recognition', anonymous=True)

    # Create Subscribers
    pcl_sub = rospy.Subscriber("/pr2/world/points", pc2.PointCloud2, pcl_callback, queue_size=1)

    # Create Publishers
    pcl_objects_pub = rospy.Publisher("/pcl_objects", PointCloud2, queue_size=1)
    pcl_table_pub = rospy.Publisher("/pcl_table", PointCloud2, queue_size=1)
    pcl_cluster_pub = rospy.Publisher("/pcl_cluster", PointCloud2, queue_size=1)
    object_markers_pub = rospy.Publisher("/object_markers", Marker, queue_size=1)
    detected_objects_pub = rospy.Publisher("/detected_objects", DetectedObjectsArray, queue_size=1)

    # Load Model From disk
    model = pickle.load(open('model.sav', 'rb'))
    clf = model['classifier']
    encoder = LabelEncoder()
    encoder.classes_ = model['classes']
    scaler = model['scaler']

    # Initialize color_list
    get_color_list.color_list = []


    # Spin while node is not shutdown
    while not rospy.is_shutdown():
        rospy.spin()

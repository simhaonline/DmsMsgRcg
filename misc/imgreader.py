import cv2
import math
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


class ImgReader(object):
    """
    This reader is to read input image(s) and convert that into an array of image features.
    """
    def __init__(self, feature_height, feature_width):
        self.feature_height = feature_height
        self.feature_width = feature_width
        self.feature_count = feature_height * feature_width

    def get_features_all_images(self, img_dir, ext_filter=['.jpg', '.png'], stride=5,
                                padding=True, data_augm=False):
        """
        Output the features extracted from all images in one folder. This method is designed only
            for the trainers.
        Args:
            img_dir: The full path to the images to be feature-extracted.
            ext_filter: Optional. File name filter.
            stride: Optional. The stride of the sliding.
            padding: Optional. Whether to pad the image to fit the feature space size or to
                discard the extra pixels if padding is False.
            data_augm: Optional. Whether to perform data augmentation for the given image. The
                only data augmentation approach applied here is to rotate 20 degree clockwise
                and rotate 20 degree anti-clockwise so that 1 image becomes 3 images.
        Returns:
            A matrix (python list), in which each row contains the features of the sampling sliding
            window, while the number of rows depends on the number of the images in the given folder
            and the image size of the input, and other parameters.
        """
        all_features = []
        for img_file in os.listdir(img_dir):
            full_path_name = os.path.join(img_dir, img_file)
            if os.path.isfile(full_path_name) and img_file.lower().endswith(tuple(ext_filter)):
                img = cv2.imread(full_path_name)
                img_arr = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, features = self.get_image_array_features(img_arr, stride, padding)
                if len(features) > 0:
                    all_features.extend(features)

                if data_augm:
                    rows, cols = img_arr.shape
                    mat1 = cv2.getRotationMatrix2D((cols / 2, rows / 2), -25, 1)
                    left_arr = cv2.warpAffine(img_arr, mat1, (cols, rows))

                    _, left_feats = self.get_image_array_features(left_arr, stride, padding)
                    if len(left_feats) > 0:
                        all_features.extend(left_feats)

                    mat2 = cv2.getRotationMatrix2D((cols / 2, rows / 2), 25, 1)
                    right_arr = cv2.warpAffine(img_arr, mat2, (cols, rows))
                    _, right_feats = self.get_image_array_features(right_arr, stride, padding)
                    if len(right_feats) > 0:
                        all_features.extend(right_feats)

        return all_features

    def get_image_features(self, img_file, stride=5, padding=True):
        """
        Take an image file as input, and output an array of image features whose matrix size is
        based on the image size. When no padding, and the image size is smaller than the required
        feature space size (in x or y direction), the image is not checked, and this method will
        return a tuple of two empty lists; When padding is True, and the image size is more than
        4 pixels smaller than the require feature space size (in x or y direction), the image is
        not checked either. This method can be used by both the trainer and predictor.
        Args:
            img_file: The file name of the image.
            stride: Optional. The stride of the sliding.
            padding: Optional. Whether to pad the image to fit the feature space size or to
                discard the extra pixels if padding is False.
        Returns:
            coordinates: A list of coordinates, each of which contains y and x that are the top
                left corner offsets of the sliding window.
            features: A matrix (python list), in which each row contains the features of the
                sampling sliding window, while the number of rows depends on the image size of
                the input.
        """
        img = cv2.imread(img_file)
        img_arr = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return self.get_image_array_features(img_arr, stride, padding)

    def get_image_array_features(self, img_arr, stride=5, padding=True):
        """
        Take an image file as input, and output an array of image features whose matrix size is
        based on the image size. When no padding, and the image size is smaller than the required
        feature space size (in x or y direction), the image is not checked, and this method will
        return a tuple of two empty lists; When padding is True, and the image size is more than
        4 pixels smaller than the require feature space size (in x or y direction), the image is
        not checked either. This method can be used by both the trainer and predictor.
        Note that when stride is greater than 5, padding is not supported, and it will be reset
        to False regardless of the input.
        Args:
            img_arr: The image array (a numpy ndarray) read from the image file. It has already
                been changed to gray scale.
            stride: Optional. The stride of the sliding.
            padding: Optional. Whether to pad the image to fit the feature space size or to
                discard the extra pixels if padding is False.
        Returns:
            coordinates: A list of coordinates, each of which contains y and x that are the top
                left corner offsets of the sliding window.
            features: A matrix (python list), in which each row contains the features of the
                sampling sliding window, while the number of rows depends on the image size of
                the input.
        """
        assert stride >= 1
        if stride > 5:
            padding = False

        coordinates, features = [], []  # two lists to be returned

        img_height, img_width = img_arr.shape
        padding_top, padding_left = 0, 0

        if not padding:
            if img_height < self.feature_height or img_width < self.feature_width:
                print("Image with size: {}x{} is too small. Ignored in when no padding."
                      .format(img_width, img_height))
                return coordinates, features
        else:
            if img_height+4 < self.feature_height or img_width+4 < self.feature_width:
                print("Image with size: {}x{} is too small. Ignored in padding mode."
                      .format(img_width, img_height))
                return coordinates, features

            if img_height > self.feature_height:
                extra_y = (img_height - self.feature_height) % stride
                if extra_y > 0:
                    padding_y = stride - extra_y
                else:
                    padding_y = 0
            elif img_height < self.feature_height:
                padding_y = self.feature_height - img_height
            else:
                padding_y = 0

            if img_width > self.feature_width:
                extra_x = (img_width - self.feature_width) % stride
                if extra_x > 0:
                    padding_x = stride - extra_x
                else:
                    padding_x = 0
            elif img_width < self.feature_width:
                padding_x = self.feature_width - img_width
            else:
                padding_x = 0

            if padding_y > 0 or padding_x > 0:
                padding_top = math.floor(padding_y / 2)
                padding_left = math.floor(padding_x / 2)

                new_y, new_x = img_height + padding_y, img_width + padding_x
                new_img = np.zeros((new_y, new_x))
                new_img[padding_top:padding_top+img_height,
                        padding_left:padding_left+img_width]=img_arr
                img_arr = new_img
                img_height, img_width = img_arr.shape

        for y in range(0, img_height-self.feature_height+1, stride):
            for x in range(0, img_width-self.feature_width+1, stride):
                orig_x = x - padding_left
                orig_y = y - padding_top
                coordinates.append((orig_y, orig_x))
                this_win = img_arr[y:y+self.feature_height, x:x+self.feature_width]
                features.append(this_win.reshape(-1))

        return coordinates, features


def plot_samples(X_images, img_height, img_width, figsize=(5, 5), transpose=True,
                 shuffle=True):
    """
    Args:
        X_images: A 2-D ndarray (matrix) each row of which holds the pixels as features
            of one image. The row number will be the number of all input images.
        img_height: The pixel numbers of the input image in height.
        img_width: The pixel numbers of the input image in width.
        figsize: Optional. The size of each small figure.
        transpose: Optional. Whether to transpose the image array. When the image attributes
            come from matlab, it needs to be transposed by default.
        shuffle: Optional. Whether to shuffle the input array.
    """
    img_cnt, feature_cnt = X_images.shape
    assert feature_cnt == img_height * img_width

    if (shuffle):
        images = np.random.permutation(X_images)
    else:
        images = X_images

    if img_cnt >= 100:
        n_row, n_col, samp_cnt = 10, 10, 100
    elif img_cnt >= 64:
        n_row, n_col, samp_cnt = 8, 8, 64
    else:
        n_row, n_col, samp_cnt = 0, 0, 0

    if img_cnt >= samp_cnt > 0:
        samps = images[0: samp_cnt]

        plt.figure(figsize=figsize)
        gs = gridspec.GridSpec(n_row, n_col, wspace=0.0, hspace=0.0)

        for i in range(0, n_row):
            for j in range(0, n_col):
                ax = plt.subplot(gs[i, j])
                idx = i * n_col + j
                img = samps[idx].reshape(img_height, img_width)
                if transpose:
                    img = img.T
                fig = ax.imshow(img, interpolation='nearest')
                fig.axes.get_xaxis().set_visible(False)
                fig.axes.get_yaxis().set_visible(False)

        plt.suptitle('{} out of {} Samples'.format(samp_cnt, img_cnt), size=12, x=0.515, y=0.935)
        plt.show()
    else:
        samps = images

        n_col = math.ceil(math.sqrt(img_cnt))
        n_row = math.ceil(img_cnt / n_col)

        fig = plt.figure(figsize=figsize)
        for i in range(0, img_cnt):
            ax = fig.add_subplot(n_row, n_col, (i + 1))
            if transpose:
                img = ax.imshow(samps[i].reshape(img_height, img_width).T)
            else:
                img = ax.imshow(samps[i].reshape(img_height, img_width))

            img.axes.get_xaxis().set_visible(False)
            img.axes.get_yaxis().set_visible(False)

        plt.suptitle('All {} Samples'.format(img_cnt), size=12, x=0.518, y=0.935)
        plt.show()


if __name__ == "__main__":
    from settings import PROJECT_ROOT

    img_reader = ImgReader(28, 28)

    img_dr = os.path.join(PROJECT_ROOT, 'Data', 'Step2', 'Training', 'TasMsg', 'Toll0')
    all_feats = img_reader.get_features_all_images(img_dr, stride=3)

    X_features = np.asarray(all_feats)
    print("X_features size: {}".format(X_features.shape))

    plot_samples(X_features, 28, 28, transpose=False, shuffle=True)
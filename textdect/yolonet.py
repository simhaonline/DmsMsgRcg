import numpy as np
import tensorflow as tf
from tensorflow import keras

from textdect.batchgenerator import BatchGenerator
from textdect.yolomodel import TinyYolo, FullYolo


class YoloNet(object):
    def __init__(self, config):
        self.config = config

        self.image_height, self.image_width = config['image_height'], config['image_width']
        self.grid_h, self.grid_w = config['grid_y_count'], config['grid_x_count']

        if config['model_architecture'] == 'Full':
            self.model = FullYolo(self.image_height, self.image_width, self.grid_h, self.grid_w).model
        elif config['model_architecture'] == 'Tiny':
            self.model = TinyYolo(self.image_height, self.image_width, self.grid_h, self.grid_w).model
        else:
            raise Exception('Architecture not supported! Only Full Yolo and Tiny Yolo are supported '
                            'at the moment!')

        if config['debug']:
            self.model.summary()

    def train(self, image_dir, train_data, weights_path_file, log_dir):
        optimizer = keras.optimizers.Adam(lr=4e-4, beta_1=0.9, beta_2=0.999,
                                          epsilon=1e-08, decay=0.0)
        self.model.compile(loss=self.custom_loss, optimizer=optimizer)

        train_batch = BatchGenerator(image_dir, train_data, self.config)

        lr_schedule = keras.callbacks.LearningRateScheduler(self.schedule)
        checkpoint = keras.callbacks.ModelCheckpoint(weights_path_file,
                                                     monitor='loss',
                                                     verbose=1,
                                                     save_best_only=True,
                                                     mode='min',
                                                     period=1)
        tensorboard = keras.callbacks.TensorBoard(log_dir=log_dir,
                                                  histogram_freq=0,
                                                  write_graph=True,
                                                  write_images=False)

        self.model.fit_generator(generator=train_batch,
                                 steps_per_epoch=len(train_batch),
                                 epochs=self.config['num_epoch'],
                                 verbose=2,
                                 callbacks=[lr_schedule, checkpoint, tensorboard],
                                 workers=3,
                                 max_queue_size=8)

    def predict(self, image):
        input_image = self.normalize(image[:, self.config['image_left_skip']:-self.config['image_right_skip'],
                                     ::-1])
        input_image = np.expand_dims(input_image, 0)

        netout = self.model.predict(input_image)[0]
        boxes = self._decode_netout(netout)

        return boxes

    def load_weights(self, weight_path_file):
        self.model.load_weights(weight_path_file)

    def _decode_netout(self, netout):
        grid_h, grid_w = netout.shape[:2]

        boxes = []
        for row in range(grid_h):
            for col in range(grid_w):
                # first 4 elements are x, y, w, and h
                x, y, w, h = netout[row, col, :4]

                x = (col + self.sigmoid(x)) * self.config['grid_x_size'] + self.config['image_left_skip']
                y = (row + self.sigmoid(y)) * self.config['grid_y_size']
                w = w * self.config['grid_x_size']
                h = h * self.config['grid_y_size']

                confidence = self.sigmoid(netout[row, col, 4])

                if self.config['debug'] and confidence > 0.1:
                    print("Net out: {}, {}, {}, {}, {}".format(x, y, w, h, confidence))

                if confidence > 0.5:
                    box = BoundBox(x, y, w, h)
                    boxes.append(box)

        return boxes

    def schedule(self, epoch_num):
        if self.config['debug'] and epoch_num > 0:
            print("# Starting epoch {:2d}, learning rate used in the last epoch = {:.6f}".
                  format(epoch_num+1, keras.backend.get_value(self.model.optimizer.lr)))

        if epoch_num < 1:
            return 4e-4
        elif epoch_num < 2:
            return 3.2e-4
        elif epoch_num < 4:
            return 2.4e-4
        elif epoch_num < 6:
            return 2e-4
        elif epoch_num < 8:
            return 1.6e-4
        elif epoch_num < 12:
            return 1.2e-4
        elif epoch_num < 18:
            return 1.1e-4
        elif epoch_num < 30:
            return 1e-4
        else:
            return 9.6e-5

    @staticmethod
    def custom_loss(y_true, y_pred):
        # Get prediction
        pred_box_xy = tf.sigmoid(y_pred[..., :2])
        pred_box_wh = y_pred[..., 2:4]
        pred_box_conf = tf.sigmoid(y_pred[..., 4])

        # Get ground truth
        true_box_xy = y_true[..., :2]
        true_box_wh = y_true[..., 2:4]
        true_box_conf = y_true[..., 4]

        # Determine the mask: simply the position of the ground truth boxes (the predictors)
        true_mask = tf.expand_dims(y_true[..., 4], axis=-1)

        # Calculate the loss. A scale is associated with each loss, indicating how important
        # the loss is. The bigger the scale, more important the loss is.
        loss_xy = tf.reduce_sum(tf.square(true_box_xy - pred_box_xy) * true_mask) * 1.0
        loss_wh = tf.reduce_sum(tf.square(true_box_wh - pred_box_wh) * true_mask) * 1.0
        loss_conf = tf.reduce_sum(tf.square(true_box_conf - pred_box_conf)) * 1.2

        loss = loss_xy + loss_wh + loss_conf
        return loss

    @staticmethod
    def normalize(image):
        return image / 255.

    @staticmethod
    def sigmoid(x):
        return 1. / (1. + np.exp(-x))


class BoundBox:
    def __init__(self, cx, cy, w, h):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h

    def get_coordinates(self):
        xmin = int(self.cx - self.w/2)
        ymin = int(self.cy - self.h/2)
        xmax = int(self.cx + self.w/2)
        ymax = int(self.cy + self.h/2)

        return xmin, ymin, xmax, ymax
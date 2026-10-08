"""Custom Keras layers shared by training (ml/train.py) and serving (app/).

The attention block is split in two so the temporal attention weights can be
read out of a trained model without touching the training graph:

    AttentionScores : (B, T, F) -> (B, T, 1)   softmax weights over time
    WeightedTimeSum : ([x, w])  -> (B, F)      attention-weighted context vector
"""
import keras
from keras import layers, ops


@keras.saving.register_keras_serializable(package="soilp")
class AttentionScores(layers.Layer):
    """Additive (Bahdanau-style) temporal attention, as in the project notebooks."""

    def build(self, input_shape):
        self.W = self.add_weight(name="W", shape=(input_shape[-1], 1),
                                 initializer="glorot_uniform", trainable=True)
        self.b = self.add_weight(name="b", shape=(input_shape[1], 1),
                                 initializer="zeros", trainable=True)
        super().build(input_shape)

    def call(self, x):
        e = ops.tanh(ops.matmul(x, self.W) + self.b)   # (B, T, 1)
        return ops.softmax(e, axis=1)

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[1], 1)


@keras.saving.register_keras_serializable(package="soilp")
class WeightedTimeSum(layers.Layer):
    def call(self, inputs):
        x, w = inputs
        return ops.sum(x * w, axis=1)

    def compute_output_shape(self, input_shape):
        return (input_shape[0][0], input_shape[0][2])


def build_model(window: int, n_features: int, cnn_filters: int, lstm_units: int, lr: float):
    """CNN -> BiLSTM -> Attention -> Dense regressor (the notebook's final architecture)."""
    inp = keras.Input(shape=(window, n_features), name="window")

    x = layers.Conv1D(cnn_filters, 3, padding="same", activation="relu")(inp)
    x = layers.BatchNormalization()(x)
    x = layers.Conv1D(cnn_filters * 2, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling1D(2)(x)
    x = layers.Dropout(0.1)(x)

    x = layers.Bidirectional(layers.LSTM(lstm_units, return_sequences=True))(x)
    x = layers.Dropout(0.1)(x)

    w = AttentionScores(name="attention_scores")(x)
    ctx = WeightedTimeSum(name="attention_context")([x, w])

    x = layers.Dense(128, activation="relu")(ctx)
    x = layers.Dropout(0.1)(x)
    out = layers.Dense(1, name="phosphorus")(x)

    model = keras.Model(inp, out, name="pso_cnn_bilstm_attention")
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=lr, clipnorm=1.0),
                  loss=keras.losses.Huber())
    return model

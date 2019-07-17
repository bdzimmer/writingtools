"""

Create book covers programatically.

"""

# Copyright (c) 2019 Ben Zimmer. All rights reserved.

import json
import os
import sys
import time

import cv2
from PIL import Image, ImageFont, ImageDraw
import numpy as np

DEBUG = True


def text_custom_kerning(text, font, color, kern_add):
    """text, controlling letter spacing"""

    letter_sizes = [font.getsize(x) for x in text]
    letter_offsets = [font.getoffset(x) for x in text]
    letter_pairs = [text[idx:(idx + 2)] for idx in range(len(text) - 1)]
    print(letter_pairs)
    letter_pair_sizes = [font.getsize(x) for x in letter_pairs]
    letter_pair_offsets = [font.getoffset(x) for x in letter_pairs]

    # kerning "width" for a letter is width of pair
    # minus the width of the individual second letter
    widths = [
        (x[0] + z[0]) - (y[0] + w[0])
        for x, y, z, w in zip(
            letter_pair_sizes, letter_sizes[1:], letter_offsets[:-1], letter_offsets[1:])]

    # add width of final letter
    widths = widths + [letter_sizes[-1][0] + letter_offsets[-1][0]]

    # TODO: this is potentially unsafe - not sure about descenders etc
    # TODO: y offset?
    # find maximum height
    height = max([x[1] for x in letter_sizes])

    offset_x_first = letter_offsets[0][0]
    width_total = sum(widths) - offset_x_first + (len(widths) - 1) * kern_add

    if DEBUG:
        print("ind widths:     ", [x[0] for x in letter_sizes])
        print("ind offsets:    ", [x[0] for x in letter_offsets])
        print("pair widths:    ", [x[0] for x in letter_pair_sizes])
        print("pair offsets:   ", [x[0] for x in letter_pair_offsets])
        print("true widths:    ", widths)
        print("sum ind. widths:", sum([x[0] for x in letter_sizes]))
        print("getsize width:  ", font.getsize(text)[0])
        print("width_total:    ", width_total)

    image = Image.new("RGBA", (width_total, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    offset = 0 - offset_x_first
    for letter, letter_width in zip(text, widths):
        draw.text((offset, 0), letter, font=font, fill=color)
        offset = offset + letter_width + kern_add

    return image


def text_standard(text, font, color):
    """standard text rendering"""

    size = font.getsize(text)
    offset = font.getoffset(text)
    image = Image.new("RGBA", (size[0], size[1]), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    # TODO: how to use offset here?
    draw.text((0 - offset[0], 0), text, font=font, fill=color)
    return image


def render_layer(layer, resources_dirname):
    """render a single layer"""

    layer_type = layer["type"]
    if layer_type == "image":
        image_pil = Image.open(
            os.path.join(resources_dirname, layer["filename"]))
        image = np.array(image_pil)
        if image.shape[2] == 3:
            image = add_alpha(image)
    elif layer_type == "gaussian":
        width = layer["width"]
        height = layer["height"]
        a = layer["a"]
        x = layer.get("x", width * 0.5)
        y = layer.get("y", height * 0.5)
        sigma_x = layer.get("sigma_x", width * 0.75)
        sigma_y = layer.get("sigma_y", height * 0.75)
        transparent = layer.get("transparent", True)

        d_x = 2.0 * sigma_x * sigma_x
        d_y = 2.0 * sigma_y * sigma_y

        ivals = np.tile(np.arange(height).reshape(-1, 1), (1, width))
        jvals = np.tile(np.arange(width), (height, 1))
        image = a * np.exp(
            0.0 - (((ivals - y) ** 2) / d_y + ((jvals - x) ** 2) / d_x))
        image = np.clip(image, 0.0, 255.0)
        image = np.array(image, dtype=np.ubyte)

        if transparent:
            black = np.zeros((height, width), dtype=np.ubyte)
            image = np.stack((black, black, black, 255 - image), axis=2)
        else:
            image = np.stack((image, image, image), axis=2)
            image = add_alpha(image)

    elif layer_type == "text":
        font = ImageFont.truetype(layer["font"], layer["size"])
        text = layer["text"]
        color = tuple(layer.get("color", (0, 0, 0, 255)))
        kern_add = layer.get("kern_add", 0)
        image = text_standard(text, font, color)
        image_custom = text_custom_kerning(text, font, color, kern_add)
        if DEBUG:
            image.save("text_" + text + "_true.png")
            image_custom.save("text_" + text + "_custom.png")
        image = np.array(image_custom)
    else:
        image = None
    return image


def add_alpha(image):
    """add an alpha channel to an image"""
    return np.concatenate(
        (image,
         np.ones((image.shape[0], image.shape[1], 1), dtype=np.ubyte) * 255),
        axis=2)


def trim(layer_image, layer_x, layer_y, canvas_width, canvas_height):
    """trim the layer to fit the canvas"""

    start_x = 0
    end_x = layer_image.shape[1]
    start_y = 0
    end_y = layer_image.shape[0]

    if layer_x < 0:
        start_x = 0 - layer_x
        layer_x = 0
    if layer_x + end_x > canvas_width:
        end_x = start_x + canvas_width

    if layer_y < 0:
        start_y = 0 - layer_y
        layer_y = 0
    if layer_y + end_y > canvas_height:
        end_y = start_y + canvas_height

    return layer_image[start_y:end_y, start_x:end_x, :], layer_x, layer_y


def apply_effect(image, effect):
    """layer effects!"""
    effect_type = effect["type"]

    if effect_type == "flip_ud":
        image = np.array(Image.fromarray(image).transpose(Image.FLIP_TOP_BOTTOM))
    elif effect_type == "blend":
        opacity = effect["opacity"]
        transparent = Image.new("RGBA", (image.shape[1], image.shape[0]), (255, 255, 255, 0))
        image = np.array(Image.blend(transparent, Image.fromarray(image), opacity))
    elif effect_type == "glow":
        dilate_size = effect.get("dilate", 16)
        blur_size = effect.get("blur", 127)
        color = tuple(effect.get("color", (0, 0, 0)))

        edge = cv2.Canny(image, 100, 200)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (dilate_size, dilate_size))
        edge = cv2.dilate(edge, kernel)
        edge = cv2.GaussianBlur(edge, (blur_size, blur_size), 0)
        color = np.array(color, dtype=np.ubyte)
        glow = np.tile(np.reshape(color, (1, 1, 3)), (image.shape[0], image.shape[1], 1))
        glow = np.concatenate((glow, np.expand_dims(edge, axis=2)), axis=2)
        glow = Image.fromarray(glow)
        glow.paste(Image.fromarray(image), (0, 0), Image.fromarray(image))
        image = np.array(glow)
    else:
        print("\tunrecognized effect type '" + str(effect_type) + "'")

    return image


def expand_border(image, border_x, border_y):
    """add a border to an image"""

    res = Image.new(
        "RGBA",
        (image.shape[1] + 2 * border_x, image.shape[0] + 2 * border_y),
        (255, 255, 255, 0))

    # not sure why this doesn't work
    # mask = Image.fromarray(image)
    # res.paste(image, (border_x, border_y), mask)

    res = np.array(res)
    lim_y = res.shape[0] - border_y if border_y > 0 else res.shape[0]
    lim_x = res.shape[1] - border_x if border_x > 0 else res.shape[1]

    res[border_y:lim_y, border_x:lim_x] = image
    return np.array(res)


def main(argv):
    """main program"""

    start_time = time.time()

    input_filename = argv[1]
    project_dirname = os.path.splitext(input_filename)[0]

    with open(input_filename, "r") as input_file:
        config = json.load(input_file)

    resources_dirname = config["resources_dirname"]
    canvas_width = config["width"]
    canvas_height = config["height"]

    os.makedirs(project_dirname, exist_ok=True)

    res = Image.new("RGB", (canvas_width, canvas_height), (255, 255, 255))

    for layer_idx, layer in enumerate(config["layers"]):
        print("layer", layer_idx, "...", end="", flush=True)

        # ~~~~ render

        layer_image = render_layer(
            layer, resources_dirname)

        # ~~~~ add borders

        border_x = layer.get("border_x", 0)
        border_y = layer.get("border_y", 0)

        if border_x > 0 or border_y > 0:
            layer_image = expand_border(layer_image, border_x, border_y)

        # ~~~~ add effects

        for effect_idx, effect in enumerate(layer.get("effects", [])):
            layer_image = apply_effect(layer_image, effect)

        # ~~~~ calculate position

        # positions are calculated from inside the border
        layer_height, layer_width, _ = layer_image.shape
        layer_width = layer_width - 2 * border_x
        layer_height = layer_height - 2 * border_y

        # layer positions default to centered on the canvas
        layer_x = layer.get(
            "x", int(canvas_width * 0.5 - layer_width * 0.5))
        layer_y = layer.get(
            "y", int(canvas_height * 0.5 - layer_height * 0.5))

        # trim and update positions
        layer_image_trimmed, layer_x, layer_y = trim(
            layer_image, layer_x, layer_y, canvas_width, canvas_height)

        # ~~~~ accumulate

        image_pil = Image.fromarray(layer_image_trimmed)
        res.paste(image_pil, (layer_x - border_x, layer_y - border_y), image_pil)

        image_pil.save(
            os.path.join(
                project_dirname, str(layer_idx).rjust(3, "0") + ".png"))

        print("done")

    res.save(
        os.path.join(
            project_dirname, "final.png"))

    end_time = time.time()
    total_time = end_time - start_time
    print("total time:", round(total_time, 3), "sec")


if __name__ == "__main__":
    main(sys.argv)

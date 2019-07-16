"""
Create book covers programatically.

"""

# Copyright (c) 2019 Ben Zimmer. All rights reserved.

import os
import json
import sys

from PIL import Image, ImageFont, ImageDraw
import numpy as np


def render_layer(layer, resources_dirname):
    # render a layer
    layer_type = layer["type"]
    if layer_type == "image":
        image_pil = Image.open(
            os.path.join(resources_dirname, layer["filename"]))
        image = np.array(image_pil)
        print(image.shape)
        if image.shape[2] == 3:
            image = add_alpha(image)
    elif layer_type == "text":
        font = ImageFont.truetype(
            layer["font"],
            layer["size"])
        text = layer["text"]
        color = tuple(layer.get("color", (0, 0, 0, 255)))
        size = font.getsize(text)
        image = Image.new("RGBA", size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), text, font=font, fill=color)
        image = np.array(image)
    else:
        image = None
    return image


def add_alpha(image):
    return np.concatenate(
        (image,
         np.ones((image.shape[0], image.shape[1], 1), dtype=np.ubyte) * 255),
        axis=2)


def trim(layer_image, layer_x, layer_y, canvas_width, canvas_height):
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
    else:
        print("\tunrecognized effect type '" + str(effect_type) + "'")

    return image


def expand_border(image, border_x, border_y):
    """add a border"""
    res = Image.new(
        "RGBA",
        (image.shape[1] + 2 * border_x, image.shape[0] + 2 * border_y),
        (255, 255, 255, 0))

    # not sure why this wasn't working
    # mask = Image.fromarray(image)
    # res.paste(image, (border_x, border_y), mask)

    res = np.array(res)
    print(res.shape, image.shape)
    lim_y = res.shape[0] - border_y if border_y > 0 else res.shape[0]
    lim_x = res.shape[1] - border_x if border_x > 0 else res.shape[1]

    res[border_y:lim_y, border_x:lim_x] = image
    return np.array(res)


def main(argv):
    """main program"""

    input_filename = argv[1]
    project_dirname = os.path.splitext(input_filename)[0]

    with open(input_filename, "r") as input_file:
        config = json.load(input_file)

    print(config)
    resources_dirname = config["resources_dirname"]
    canvas_width = config["width"]
    canvas_height = config["height"]

    os.makedirs(project_dirname, exist_ok=True)

    res = Image.new("RGB", (canvas_width, canvas_height), (255, 255, 255))

    for layer_idx, layer in enumerate(config["layers"]):

        # ~~~~ render

        layer_image = render_layer(
            layer, resources_dirname)
        print(layer_image.shape)

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
                project_dirname, str(layer_idx).rjust(3) + ".png"))

    res.save(
        os.path.join(
            project_dirname, "final.png"))


if __name__ == "__main__":
    main(sys.argv)

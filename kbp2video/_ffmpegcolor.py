#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ffmpeg.nodes import FilterableStream, FilterNode, Node
__all__ = ["ffmpeg_color"]

# Special version of filternode to allow for color filter to work
# despite having 0 inputs
class FilterNode2(FilterNode):
     def __init__(self, stream_spec, name, max_inputs=1, args=[], kwargs={}):
             Node.__init__(
                self,
                stream_spec=stream_spec,
                name=name,
                incoming_stream_types={FilterableStream},
                outgoing_stream_type=FilterableStream,
                min_inputs=0, # << This is required for color filter to work
                max_inputs=max_inputs,
                args=args,
                kwargs=kwargs,
            )

def ffmpeg_color(*args, **kwargs):
    return FilterNode2(
        None,
        "color",
        args=args,
        kwargs=kwargs,
        max_inputs=None).stream()

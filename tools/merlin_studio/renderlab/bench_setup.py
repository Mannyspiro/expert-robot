import bpy
s = bpy.context.scene
s.render.resolution_percentage = 50
s.render.resolution_x = 960
s.render.resolution_y = 540
s.cycles.samples = 8
s.cycles.use_denoising = False
s.cycles.device = "CPU"
s.render.image_settings.file_format = "PNG"

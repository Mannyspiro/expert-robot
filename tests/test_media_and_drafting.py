import unittest
from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.cad_assembly import AssemblyComponent, CADAssembly, Transform3D
from merlin.media_generation import EngineeringMediaBrief, compile_engineering_prompts, _replace_prompt_tokens
from merlin.engineering_drafting import export_route_elevation_svg, export_top_view_svg


class MediaAndDraftingTests(unittest.TestCase):
    def setUp(self):
        self.project = EngineeringProject(
            "demo", "mm",
            (Part("J1", "connector", (Pin("1", "VIN", position_mm=(10, 0, 0)),), size_mm=(20, 10, 4)),
             Part("U1", "controller", (Pin("1", "VCC", position_mm=(-6, 0, 0)),), size_mm=(12, 8, 2))),
            (Net("VIN", ("J1.1", "U1.1"), 5.0, 0.2, "power"),),
        )
        self.assembly = CADAssembly(
            "demo-assembly",
            (AssemblyComponent("J1", Transform3D(translation_mm=(0, 0, 0))),
             AssemblyComponent("U1", Transform3D(translation_mm=(30, 0, 0)))),
        )
        self.route_output = {
            "format": "merlin-wire-route-proposals-v0.1",
            "units": "mm",
            "project": "demo",
            "assembly": "demo-assembly",
            "nets": [{
                "name": "VIN",
                "status": "candidate_geometry_not_manufacturing_qualified",
                "routes": [{
                    "from": "J1.1", "to": "U1.1",
                    "status": "candidate_geometry_not_manufacturing_qualified",
                    "method": "global_z_overpass",
                    "polyline_mm": [[10, 0, 0], [10, 0, 8], [24, 0, 8], [24, 0, 0]],
                }],
            }],
            "status": "GEOMETRY_PROPOSAL_ONLY_NOT_ELECTRICAL_OR_MANUFACTURING_APPROVAL",
        }

    def test_prompt_pack_is_bound_to_exact_source_facts(self):
        pack = compile_engineering_prompts(
            self.project, EngineeringMediaBrief("demo", "assembly review"), self.assembly)
        self.assertIn("J1 connector", pack.image_prompt)
        self.assertIn("J1.1", pack.video_prompt)
        self.assertIn('"units": "mm"', pack.coder_prompt)
        self.assertIn("not_engineering_source", pack.status.lower())

    def test_prompts_do_not_claim_missing_wire_specs(self):
        pack = compile_engineering_prompts(
            self.project, EngineeringMediaBrief("demo", "review"), self.assembly)
        self.assertIn("unverified wire gauge", pack.negative_prompt)
        self.assertNotIn("AWG", pack.image_prompt)

    def test_prompt_limits(self):
        with self.assertRaises(ValueError):
            compile_engineering_prompts(self.project,
                EngineeringMediaBrief("demo", "review", duration_seconds=60))

    def test_comfy_workflow_token_replacement(self):
        source = {"1": {"inputs": {"text": "{{PROMPT}}", "negative": "{{NEGATIVE_PROMPT}}"}}}
        result = _replace_prompt_tokens(source, "exact geometry", "no fake text")
        self.assertEqual(result["1"]["inputs"]["text"], "exact geometry")
        self.assertEqual(result["1"]["inputs"]["negative"], "no fake text")
        self.assertEqual(source["1"]["inputs"]["text"], "{{PROMPT}}")

    def test_top_view_svg_uses_declared_geometry_and_is_labelled(self):
        svg = export_top_view_svg(self.project, self.assembly)
        self.assertIn("NOT FOR MANUFACTURE", svg)
        self.assertIn("NOT ROUTED", svg)
        self.assertIn('stroke-dasharray="4 3"', svg)
        self.assertIn("J1", svg)
        self.assertIn("U1", svg)
        self.assertIn('width="', svg)
        self.assertIn('viewBox=', svg)


    def test_top_view_projects_3d_route_and_preserves_z_metadata(self):
        svg = export_top_view_svg(self.project, self.assembly, route_output=self.route_output)
        self.assertIn("XY PROJECTION (Z COLLAPSED)", svg)
        self.assertIn('data-z-profile="0.000,8.000,8.000,0.000"', svg)
        self.assertIn('data-route-method="global_z_overpass"', svg)
        self.assertNotIn("NOT ROUTED", svg)

    def test_route_elevation_svg_shows_vertical_overpass(self):
        svg = export_route_elevation_svg(self.route_output, "VIN")
        self.assertIn("Z ELEVATION (mm): 0.000 to 8.000", svg)
        self.assertIn("CUMULATIVE CENTERLINE DISTANCE (mm)", svg)
        self.assertIn('data-route-method="global_z_overpass"', svg)

    def test_drafting_rejects_route_for_another_project(self):
        wrong = dict(self.route_output)
        wrong["project"] = "other-project"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            export_top_view_svg(self.project, self.assembly, route_output=wrong)

    def test_drafting_rejects_nonfinite_route_geometry(self):
        wrong = dict(self.route_output)
        wrong["nets"] = [dict(self.route_output["nets"][0])]
        wrong["nets"][0]["routes"] = [dict(wrong["nets"][0]["routes"][0])]
        wrong["nets"][0]["routes"][0]["polyline_mm"] = [[10, 0, 0], [float("nan"), 0, 0]]
        with self.assertRaisesRegex(ValueError, "finite"):
            export_top_view_svg(self.project, self.assembly, route_output=wrong)



if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.graph import UnitGraph
from core.registry import SkillRegistry
from core.planner import Planner
from core.validator import GraphValidator, TaskGraphValidator
from core.orchestrator import Orchestrator, TaskResult


class EchoExecutor:
    def execute(self, task, context):
        return TaskResult(True, [f"artifacts/{task.id}.json"], requires_review=False)


class KernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = SkillRegistry.load(ROOT / "skills")
        cls.planner = Planner(cls.registry)

    def short_graph(self):
        return UnitGraph.from_dict({"units": [
            {"id":"P","kind":"project","parent":None,"children":["SEQ1"]},
            {"id":"SEQ1","kind":"sequence","parent":"P","children":["SC1"]},
            {"id":"SC1","kind":"scene","parent":"SEQ1","children":["B1"]},
            {"id":"B1","kind":"beat","parent":"SC1","children":["SH1","SH2"]},
            {"id":"SH1","kind":"shot","parent":"B1","children":[]},
            {"id":"SH2","kind":"shot","parent":"B1","children":[]}
        ]})

    def film_graph(self):
        return UnitGraph.from_dict({"units": [
            {"id":"P","kind":"project","parent":None,"children":["A1"]},
            {"id":"A1","kind":"act","parent":"P","children":["SEQ1","SEQ2"]},
            {"id":"SEQ1","kind":"sequence","parent":"A1","children":["SC1"]},
            {"id":"SEQ2","kind":"sequence","parent":"A1","children":["SC2"]},
            {"id":"SC1","kind":"scene","parent":"SEQ1","children":["B1"]},
            {"id":"SC2","kind":"scene","parent":"SEQ2","children":["B2"]},
            {"id":"B1","kind":"beat","parent":"SC1","children":["SH1"]},
            {"id":"B2","kind":"beat","parent":"SC2","children":["SH2"]},
            {"id":"SH1","kind":"shot","parent":"B1","children":[]},
            {"id":"SH2","kind":"shot","parent":"B2","children":[]}
        ]})

    def project(self, profile, **features):
        return {
            "id":"TEST","title":"Test","profile":profile,"language":"th",
            "intent":{"promise":"test"},
            "delivery":{"width":1920,"height":1080,"fps":30},
            "features":features,
            "source_refs":[]
        }

    def test_short_stays_small(self):
        project=self.project("short-90s", infographic=True, narration=True)
        plan=self.planner.plan(project,self.short_graph())
        active={k:v for k,v in plan["activation"].items() if v in {"required","inline"}}
        self.assertIn("director",active)
        self.assertIn("motion-vfx",active)
        self.assertIn("sound",active)
        self.assertNotIn("cinematography",active)
        self.assertNotIn("production-design",active)
        self.assertNotIn("performance",active)
        self.assertLessEqual(len(plan["tasks"]),12)

    def test_bootstrap_defers_downstream_until_units_exist(self):
        graph=UnitGraph.from_dict({"units":[{"id":"P","kind":"project","parent":None,"children":[]}]})
        plan=self.planner.plan(self.project("short-90s",infographic=True,narration=True),graph)
        skills={t["skill_id"] for t in plan["tasks"]}
        self.assertIn("producer",skills)
        self.assertIn("story",skills)
        self.assertNotIn("editor",skills)
        self.assertNotIn("qc",skills)

    def test_optional_not_scheduled(self):
        project=self.project("short-90s")
        plan=self.planner.plan(project,self.short_graph())
        storyboard=[t for t in plan["tasks"] if t["skill_id"]=="storyboard"]
        self.assertEqual(storyboard,[])

    def test_film_expands(self):
        project=self.project("film", characters=True, dialogue=True, generated_video=True, cinematic=True)
        plan=self.planner.plan(project,self.film_graph())
        active={k:v for k,v in plan["activation"].items() if v in {"required","inline"}}
        for skill in ["producer","story","director","storyboard","cinematography","production-design","performance","sound","editor","continuity","color-finishing","qc"]:
            self.assertIn(skill,active)
        self.assertGreater(len(plan["tasks"]),12)

    def test_master_signature_changes_when_graph_expands(self):
        project=self.project("short-90s",infographic=True,narration=True)
        graph1=self.short_graph()
        tasks1={task.id:task for task in self.planner.build_tasks(project,graph1)}
        master1=tasks1["editor@MASTER"].signature()
        data=graph1.to_dict()
        for unit in data["units"]:
            if unit["id"]=="P":
                unit["children"].append("SEQ2")
        data["units"].extend([
            {"id":"SEQ2","kind":"sequence","parent":"P","children":["SC2"],"refs":{}},
            {"id":"SC2","kind":"scene","parent":"SEQ2","children":["B2"],"refs":{}},
            {"id":"B2","kind":"beat","parent":"SC2","children":["SH3"],"refs":{}},
            {"id":"SH3","kind":"shot","parent":"B2","children":[],"refs":{}}
        ])
        graph2=UnitGraph.from_dict(data)
        tasks2={task.id:task for task in self.planner.build_tasks(project,graph2)}
        self.assertNotEqual(master1,tasks2["editor@MASTER"].signature())

    def test_graph_profile_validation(self):
        profile=yaml.safe_load((ROOT/"profiles/short-90s.yaml").read_text())
        issues=GraphValidator().validate(self.short_graph(),profile)
        self.assertEqual([i for i in issues if i.severity=="error"],[])

    def test_task_dag_valid(self):
        tasks=self.planner.build_tasks(self.project("film",characters=True,dialogue=True,generated_video=True),self.film_graph())
        issues=TaskGraphValidator().validate(tasks,self.registry)
        self.assertEqual([i for i in issues if i.severity=="error"],[])

    def test_orchestrator_executes_dag(self):
        tasks=self.planner.build_tasks(self.project("short-90s",infographic=True,narration=True),self.short_graph())
        orch=Orchestrator(tasks)
        executor=EchoExecutor()
        guard=0
        while not orch.is_complete():
            ready=orch.ready_tasks()
            self.assertTrue(ready,"DAG deadlocked")
            for task in ready:
                orch.run_one(task.id,executor,{})
            guard+=1
            self.assertLess(guard,20)
        self.assertTrue(orch.snapshot()["complete"])


if __name__ == "__main__":
    unittest.main()

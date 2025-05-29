from time import sleep

import requests

from rgs_utils.models import enums, EnumSourceType

project_id = 1
workflow_type = enums.EnumWorkflowType.IMPORT

workflow_id = 1  # or new

action = "api"  # (step_code)

# step 1, create workflow - import
response = requests.post(
    f"http://localhost:8000/api/v1/project/{project_id}/{workflow_type}/",
    json={
        "source_type": EnumSourceType.FILE,
    },
    files={"file": open("file.csv", "rb")},
)

out = response.json()
out = {
    "workflow_id": out["workflow_id"],
    "step": out["step"],
    "task_id": out["task_id"],
    "task_progress_url": f"http://localhost:8000/api/v1/project/{project_id}/{workflow_type}/{workflow_id}/progress/{task_id}/",
}

ready = False
new_out = None
while not ready:
    sleep(1)
    response = requests.get(out["task_progress_url"])
    new_out = response.json()
    if new_out["status"] == "ready":
        ready = True
    else:
        print(new_out)

new_out = {
    "status": "ready",
    "workflow_id": new_out["workflow_id"],
    "next_step": new_out["step"],
    "step_url": f"http://localhost:8000/api/v1/project/{project_id}/{workflow_type}/{workflow_id}/{new_out['step']}/",
}


out = response.json()


print(out)

out.task_id


requests.get(f"http://localhost:8000/api/v1/project/{project_id}/{workflow_type}/{workflow_id}/{action}/")

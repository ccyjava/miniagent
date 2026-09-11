"""Daemon mode: the agent that never stops.

Watches tasks_dir for new `<name>.task` files (plain text = the task).
Each task is executed, the result is appended, and the file is moved to
tasks_dir/done/<name>.task.done. The loop itself runs forever; one bad
task can never kill it.
"""
import os
import time
import traceback


def serve(make_agent, tasks_dir, poll=5, hooks=None):
    os.makedirs(tasks_dir, exist_ok=True)
    os.makedirs(os.path.join(tasks_dir, "done"), exist_ok=True)
    if hooks:
        hooks.fire("SessionStart", {"mode": "daemon", "tasks_dir": tasks_dir})
    print(f"[miniagent] daemon running, watching {tasks_dir} (Ctrl-C to stop)",
          flush=True)
    try:
        while True:  # <- never stops
            try:
                for fname in sorted(os.listdir(tasks_dir)):
                    if not fname.endswith(".task"):
                        continue
                    path = os.path.join(tasks_dir, fname)
                    _run_one(make_agent, path, tasks_dir)
            except Exception:
                traceback.print_exc()  # keep going no matter what
            time.sleep(poll)
    except KeyboardInterrupt:
        print("\n[miniagent] daemon stopped by user")
    finally:
        if hooks:
            hooks.fire("SessionEnd", {"mode": "daemon"})


def _run_one(make_agent, path, tasks_dir):
    with open(path, encoding="utf-8") as f:
        task = f.read().strip()
    name = os.path.basename(path)
    print(f"[miniagent] picked up task: {name}", flush=True)
    try:
        result = make_agent().run(task)
    except Exception as e:
        result = f"TASK FAILED: {type(e).__name__}: {e}\n{traceback.format_exc()}"
    done = os.path.join(tasks_dir, "done", name + ".done")
    with open(done, "w", encoding="utf-8") as f:
        f.write(f"# task\n{task}\n\n# result\n{result}\n")
    os.remove(path)
    print(f"[miniagent] finished: {name} -> {done}", flush=True)

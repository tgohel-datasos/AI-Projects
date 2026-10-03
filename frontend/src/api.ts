export type AgentExecution = {
  id: string;
  agent_id: string;
  stage: string;
  status: string;
  attempt: number;
  error: string | null;
  output: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
};

export type Workflow = {
  id: string;
  status: string;
  selected_agents: string[];
  dag: { stage: string; agents: string[]; mode: string }[];
  error: string | null;
  request: Record<string, unknown>;
  executions: AgentExecution[];
  plan: { id: string; feasibility: string; summary: Record<string, unknown> } | null;
};

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function createPlan(body: unknown): Promise<Workflow> {
  const res = await fetch(`${API}/api/plans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export async function getWorkflow(id: string): Promise<Workflow> {
  const res = await fetch(`${API}/api/workflows/${id}`);
  if (!res.ok) throw new Error("Workflow not found");
  return res.json();
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { ListChecks, Loader2, Play, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useCan } from "@/lib/auth/can";
import {
  addExpertiseParticipant,
  EXPERTISE_PARTICIPANT_ROLE_LABELS,
  getExpertiseParticipants,
  getExpertiseTasks,
  listEmployees,
  listWorkflowTemplates,
  removeExpertiseParticipant,
  startExpertiseWorkflow,
  type EmployeeOption,
  type ExpertiseParticipantResponse,
  type ExpertiseParticipantRole,
  type ExpertiseTaskSummary,
  type WorkflowOption,
} from "@/lib/api/expertises";

const TASK_STATUS_LABELS: Record<string, string> = {
  new: "Новая",
  in_progress: "В работе",
  completed: "Выполнена",
  cancelled: "Отменена",
};

export function ExpertiseCollaboration({ expertiseId }: { expertiseId: string }) {
  const canAssign = useCan("expertises.assign_experts");
  const canEdit = useCan("expertises.edit");

  const [participants, setParticipants] = useState<ExpertiseParticipantResponse[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [tasks, setTasks] = useState<ExpertiseTaskSummary[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowOption[]>([]);

  const [employeeId, setEmployeeId] = useState("");
  const [role, setRole] = useState<ExpertiseParticipantRole>("specialist");
  const [workflowTemplateId, setWorkflowTemplateId] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const controller = new AbortController();
    Promise.all([
      getExpertiseParticipants(expertiseId, { signal: controller.signal }),
      listEmployees({ signal: controller.signal }),
      getExpertiseTasks(expertiseId, { signal: controller.signal }),
      canEdit ? listWorkflowTemplates({ signal: controller.signal }) : Promise.resolve([]),
    ])
      .then(([p, emps, t, wf]) => {
        setParticipants(p);
        setEmployees(emps);
        setTasks(t);
        setWorkflows(wf);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof ApiError ? caught.detail : "Не удалось загрузить раздел.");
      });
    return () => controller.abort();
  }, [expertiseId, canEdit]);

  useEffect(() => load(), [load]);

  const addParticipant = async () => {
    if (!employeeId) return;
    setBusy(true);
    setError(null);
    try {
      await addExpertiseParticipant(expertiseId, {
        employee_id: employeeId,
        participation_role: role,
      });
      setEmployeeId("");
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось добавить участника.");
    } finally {
      setBusy(false);
    }
  };

  const removeParticipant = async (participantEmployeeId: string) => {
    setBusy(true);
    setError(null);
    try {
      await removeExpertiseParticipant(expertiseId, participantEmployeeId);
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось удалить участника.");
    } finally {
      setBusy(false);
    }
  };

  const startWorkflow = async () => {
    if (!workflowTemplateId) return;
    setBusy(true);
    setError(null);
    try {
      await startExpertiseWorkflow(expertiseId, workflowTemplateId);
      setWorkflowTemplateId("");
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Не удалось запустить процесс.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="h-4 w-4" />
            Участники
          </CardTitle>
        </CardHeader>
        <CardContent>
          {participants.length === 0 ? (
            <p className="text-sm text-muted-foreground">Дополнительные участники не назначены.</p>
          ) : (
            <ul className="divide-y divide-border">
              {participants.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="text-sm text-foreground">
                    {p.employee_name ?? "—"}
                    {p.position ? ` — ${p.position}` : ""}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">
                      {EXPERTISE_PARTICIPANT_ROLE_LABELS[p.participation_role]}
                    </span>
                    {canAssign && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() => removeParticipant(p.employee_id)}
                      >
                        Убрать
                      </Button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {canAssign && (
            <div className="mt-4 flex flex-wrap items-end gap-2">
              <div className="min-w-48 flex-1 space-y-1">
                <label className="text-xs text-muted-foreground">Сотрудник</label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  disabled={busy}
                >
                  <option value="">Выберите сотрудника</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.full_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Роль</label>
                <select
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={role}
                  onChange={(e) => setRole(e.target.value as ExpertiseParticipantRole)}
                  disabled={busy}
                >
                  <option value="specialist">Специалист</option>
                  <option value="expert">Эксперт</option>
                </select>
              </div>
              <Button onClick={addParticipant} disabled={busy || !employeeId}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Добавить"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ListChecks className="h-4 w-4" />
            Связанные задачи
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">Связанных задач нет.</p>
          ) : (
            <ul className="divide-y divide-border">
              {tasks.map((task) => (
                <li key={task.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="text-sm text-foreground">{task.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {TASK_STATUS_LABELS[task.status] ?? task.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {canEdit && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Play className="h-4 w-4" />
              Процесс
            </CardTitle>
          </CardHeader>
          <CardContent>
            {workflows.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Нет опубликованных workflow-шаблонов для запуска.
              </p>
            ) : (
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-56 flex-1 space-y-1">
                  <label className="text-xs text-muted-foreground">Workflow-шаблон</label>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={workflowTemplateId}
                    onChange={(e) => setWorkflowTemplateId(e.target.value)}
                    disabled={busy}
                  >
                    <option value="">Выберите шаблон</option>
                    {workflows.map((wf) => (
                      <option key={wf.id} value={wf.id}>
                        {wf.name}
                      </option>
                    ))}
                  </select>
                </div>
                <Button onClick={startWorkflow} disabled={busy || !workflowTemplateId}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Запустить процесс"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

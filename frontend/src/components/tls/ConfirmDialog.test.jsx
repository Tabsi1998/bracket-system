import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { ConfirmDialogProvider, useConfirm, usePrompt } from "./ConfirmDialog";

function ConfirmHarness(options) {
  const confirm = useConfirm();
  const [result, setResult] = useState("offen");
  return (
    <div>
      <button type="button" onClick={async () => setResult(String(await confirm(options)))}>
        Löschen
      </button>
      <output data-testid="result">{result}</output>
    </div>
  );
}

function PromptHarness(options) {
  const prompt = usePrompt();
  const [result, setResult] = useState("offen");
  return (
    <div>
      <button type="button" onClick={async () => setResult(String(await prompt(options)))}>
        Grund erfassen
      </button>
      <output data-testid="result">{result}</output>
    </div>
  );
}

function renderConfirm(options) {
  return render(
    <ConfirmDialogProvider>
      <ConfirmHarness {...options} />
    </ConfirmDialogProvider>
  );
}

function renderPrompt(options) {
  return render(
    <ConfirmDialogProvider>
      <PromptHarness {...options} />
    </ConfirmDialogProvider>
  );
}

test("Bestätigen löst die Aktion mit true auf", async () => {
  const user = userEvent.setup();
  renderConfirm();

  await user.click(screen.getByRole("button", { name: "Löschen" }));
  await user.click(screen.getByTestId("confirm-dialog-confirm"));

  await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("true"));
  expect(screen.queryByTestId("confirm-dialog")).not.toBeInTheDocument();
});

test("Abbrechen löst mit false auf", async () => {
  const user = userEvent.setup();
  renderConfirm();

  await user.click(screen.getByRole("button", { name: "Löschen" }));
  await user.click(screen.getByTestId("confirm-dialog-cancel"));

  await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("false"));
});

test("Escape bricht ab, statt die Aktion auszuführen", async () => {
  const user = userEvent.setup();
  renderConfirm();

  await user.click(screen.getByRole("button", { name: "Löschen" }));
  expect(screen.getByTestId("confirm-dialog")).toBeInTheDocument();

  await user.keyboard("{Escape}");

  await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("false"));
  expect(screen.queryByTestId("confirm-dialog")).not.toBeInTheDocument();
});

test("Klick auf den Hintergrund bricht ab", async () => {
  const user = userEvent.setup();
  renderConfirm();

  await user.click(screen.getByRole("button", { name: "Löschen" }));
  await user.click(screen.getByRole("presentation"));

  await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("false"));
});

test("Der Dialog übernimmt den Fokus und gibt ihn danach zurück", async () => {
  const user = userEvent.setup();
  renderConfirm();
  const trigger = screen.getByRole("button", { name: "Löschen" });

  await user.click(trigger);
  await waitFor(() => expect(screen.getByTestId("confirm-dialog").contains(document.activeElement)).toBe(true));

  await user.keyboard("{Escape}");

  await waitFor(() => expect(trigger).toHaveFocus());
});

test("Eigene Beschriftungen werden angezeigt", async () => {
  const user = userEvent.setup();
  renderConfirm({ title: "Turnier verwerfen", confirmLabel: "Endgültig löschen", cancelLabel: "Behalten" });

  await user.click(screen.getByRole("button", { name: "Löschen" }));

  expect(screen.getByText("Turnier verwerfen")).toBeInTheDocument();
  expect(screen.getByTestId("confirm-dialog-confirm")).toHaveTextContent("Endgültig löschen");
  expect(screen.getByTestId("confirm-dialog-cancel")).toHaveTextContent("Behalten");
});

test("Die Eingabe des Prompts wird zurückgegeben", async () => {
  const user = userEvent.setup();
  renderPrompt({ multiline: false });

  await user.click(screen.getByRole("button", { name: "Grund erfassen" }));
  await user.keyboard("Regelverstoss");
  await user.click(screen.getByTestId("confirm-dialog-confirm"));

  await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("Regelverstoss"));
});

test("Ein Pflicht-Prompt lässt sich nicht leer bestätigen", async () => {
  const user = userEvent.setup();
  renderPrompt({ required: true, multiline: false });

  await user.click(screen.getByRole("button", { name: "Grund erfassen" }));
  expect(screen.getByTestId("confirm-dialog-confirm")).toBeDisabled();

  await user.keyboard("Grund");

  expect(screen.getByTestId("confirm-dialog-confirm")).toBeEnabled();
});

test("Das Eingabefeld des Prompts bekommt den Fokus", async () => {
  const user = userEvent.setup();
  renderPrompt({ multiline: false, placeholder: "Grund" });

  await user.click(screen.getByRole("button", { name: "Grund erfassen" }));

  await waitFor(() => expect(screen.getByPlaceholderText("Grund")).toHaveFocus());
});

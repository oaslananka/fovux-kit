import childProcess from "node:child_process";

export function unsafeExec(userInput: string): void {
  // ruleid: fovux.typescript.interpolated-child-process-exec
  childProcess.exec(`tool ${userInput}`);
}

export function unsafeExecConcat(userInput: string): void {
  // ruleid: fovux.typescript.interpolated-child-process-exec
  childProcess.exec("tool " + userInput);
}

export function safeSpawn(userInput: string): void {
  // ok: fovux.typescript.interpolated-child-process-exec
  childProcess.spawn("tool", [userInput], { shell: false });
}

export function unsafeEval(source: string): unknown {
  // ruleid: fovux.typescript.dynamic-code-execution
  return eval(source);
}

export function unsafeFunction(source: string): Function {
  // ruleid: fovux.typescript.dynamic-code-execution
  return new Function(source);
}

export function safeParse(source: string): unknown {
  // ok: fovux.typescript.dynamic-code-execution
  return JSON.parse(source);
}

export function unsafeTokenLog(authToken: string): void {
  // ruleid: fovux.typescript.credential-logging
  console.log(authToken);
}

export function safeStatusLog(status: string): void {
  // ok: fovux.typescript.credential-logging
  console.log(status);
}

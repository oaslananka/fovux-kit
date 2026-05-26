import { ExtensionFovuxClient } from "./extensionClient";

export class EmbeddedMcpClient {
  constructor(private readonly clientFactory = ExtensionFovuxClient.create) {}

  async callTool<T>(name: string, args: Record<string, unknown>): Promise<T> {
    const client = await this.clientFactory();
    return client.invokeTool<T>(name, args);
  }
}

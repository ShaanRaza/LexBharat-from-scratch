// An API failure in the one error format (docs/API.md).
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}


export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type StreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

export async function streamJobSearch(
  resumeText: string,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ resume_text: resumeText }),
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = Array.isArray(payload.detail)
          ? payload.detail.map((item: { msg?: string }) => item.msg).join(', ')
          : String(payload.detail);
      }
    } catch {
      // Keep fallback message.
    }
    throw new Error(message);
  }

  if (!response.body) {
    throw new Error('Streaming is not supported by this browser.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() || '';

    for (const chunk of chunks) {
      const lines = chunk.split('\n');
      const eventLine = lines.find((line) => line.startsWith('event:'));
      const dataLine = lines.find((line) => line.startsWith('data:'));

      if (!eventLine || !dataLine) continue;

      const event = eventLine.replace('event:', '').trim();
      const rawData = dataLine.replace('data:', '').trim();
      try {
        onEvent({ event, data: JSON.parse(rawData) });
      } catch {
        onEvent({ event: 'error', data: { message: 'Invalid stream payload.' } });
      }
    }
  }
}

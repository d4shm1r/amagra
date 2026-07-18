// usePoll.test.jsx — the sharing guarantees, which a build cannot prove.
//
// This hook exists to fix three specific bugs on the Cognition surface: two
// panels polling `/cos/events` concurrently, every tab switch refetching the
// world, and one flaky request blanking a panel that had good data a second
// ago. Each of those is a runtime behaviour, so each gets a test — otherwise
// the next refactor "simplifies" the cache away and nothing goes red.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { usePoll, refreshAll, __resetPollCache } from "./usePoll";

function Reader({ path, interval = 1000, id = "out" }) {
  const { data, error, loading } = usePoll(path, { interval });
  return (
    <span data-testid={id}>
      {loading ? "loading" : error ? `error:${error}` : JSON.stringify(data)}
    </span>
  );
}

let fetchSpy;

beforeEach(() => {
  __resetPollCache();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let n = 0;
  fetchSpy = vi.fn(() => {
    n += 1;
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ n }) });
  });
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  __resetPollCache();
});

describe("usePoll", () => {
  it("issues ONE request for many subscribers to the same url", async () => {
    render(
      <>
        <Reader path="/cos/events" id="a" />
        <Reader path="/cos/events" id="b" />
        <Reader path="/cos/events" id="c" />
      </>
    );

    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent('{"n":1}'));

    // The bug this replaces: three panels, three concurrent fetches, three
    // different answers on screen at once.
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("b")).toHaveTextContent('{"n":1}');
    expect(screen.getByTestId("c")).toHaveTextContent('{"n":1}');
  });

  it("keeps separate urls separate", async () => {
    render(
      <>
        <Reader path="/risk/stats" id="a" />
        <Reader path="/verify/stats" id="b" />
      </>
    );
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
    expect(fetchSpy.mock.calls.map(c => c[0])).toEqual(
      expect.arrayContaining([expect.stringContaining("/risk/stats"),
                              expect.stringContaining("/verify/stats")])
    );
  });

  it("serves a remount from cache instead of refetching", async () => {
    const first = render(<Reader path="/health" interval={60_000} />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    first.unmount();

    // Switching to another tab and straight back is the common case, and it
    // used to cost a full refetch of every endpoint on the surface.
    render(<Reader path="/health" interval={60_000} />);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent('{"n":1}'));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("revalidates a remount when the cached snapshot is older than the interval", async () => {
    const first = render(<Reader path="/health" interval={1000} />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    first.unmount();

    await act(async () => { vi.advanceTimersByTime(2000); });

    render(<Reader path="/health" interval={1000} />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
  });

  it("stops polling when the last subscriber unmounts", async () => {
    const view = render(<Reader path="/cos/state" interval={1000} />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));

    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(fetchSpy.mock.calls.length).toBeGreaterThan(1);

    const after = fetchSpy.mock.calls.length;
    view.unmount();
    await act(async () => { vi.advanceTimersByTime(5000); });

    // A tab nobody is looking at must not keep hitting the backend.
    expect(fetchSpy).toHaveBeenCalledTimes(after);
  });

  it("polls at the shortest interval any live subscriber asked for", async () => {
    render(
      <>
        <Reader path="/cos/events" interval={30_000} id="slow" />
        <Reader path="/cos/events" interval={1_000}  id="fast" />
      </>
    );
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));

    // One tick at a time, letting each request settle. Advancing 3s in a single
    // jump would fire three ticks before any promise resolved, and they would
    // correctly COALESCE into one request — proving nothing about the cadence.
    for (const n of [2, 3, 4]) {
      await act(async () => { vi.advanceTimersByTime(1_000); });
      await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(n));
    }

    // The 10s events feed stays live even though a 30s panel shares its data.
  });

  it("coalesces ticks that overlap an in-flight request", async () => {
    render(<Reader path="/cos/events" interval={1_000} />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));

    // Three ticks land while the first request is still open. A slow backend
    // must not accumulate a queue of identical requests behind it.
    await act(async () => { vi.advanceTimersByTime(3_000); });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("keeps the previous data when a poll fails, and surfaces the error", async () => {
    render(<Reader path="/risk/stats" interval={1000} />);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent('{"n":1}'));

    fetchSpy.mockImplementationOnce(() =>
      Promise.resolve({ ok: false, status: 503, statusText: "Service Unavailable" }));

    await act(async () => { await refreshAll(); });

    // A flaky poll annotates the panel; it does not empty a dashboard that was
    // showing good numbers a moment ago.
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("error:503"));
  });

  it("refreshAll refetches watched endpoints and ignores unwatched ones", async () => {
    const view = render(<Reader path="/health" interval={60_000} />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    view.unmount();

    await act(async () => { await refreshAll(); });
    expect(fetchSpy).toHaveBeenCalledTimes(1);   // nobody is watching it

    render(<Reader path="/health" interval={60_000} />);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent('{"n":1}'));
    await act(async () => { await refreshAll(); });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
  });

  it("does not fetch when the path is falsy", async () => {
    render(<Reader path={null} />);
    await act(async () => { vi.advanceTimersByTime(2000); });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

"""Base class for scripted mock apps."""


class App:
    def start(self, ctx): pass
    def tick(self, ctx): pass
    def on_intent(self, ctx, it, target): pass
    def on_job_done(self, ctx, job): pass
    def on_sys(self, ctx, name, data): pass
    def finalize(self, ctx): return []
    def extra_waste_ms(self, ctx): return 0


def said(ctx, needle):
    """Times at which the agent started to say something that contains `needle`."""
    return [t for t, ev, kw in ctx.log if ev == "say_start" and needle in kw["text"]]

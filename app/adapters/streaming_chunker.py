
import re, time

SENTENCE_END = re.compile(r'([.!?]["\')\]]*\s+)')   # keeps punctuation
MIN_CHARS     = 30      # don’t flush tiny bits
MAX_CHARS     = 100     # soft-flush limit
SOFT_WAIT     = 0.35    # seconds since last token → flush anyway

class StreamingChunker:
    def __init__(self):
        self.buf, self.last_flush = '', time.monotonic()

    def feed(self, txt:str) -> list[str]:
        self.buf += txt
        chunks, start = [], 0

        # ① Hard break on punctuation if we already have enough chars
        for m in SENTENCE_END.finditer(self.buf):
            if m.end()-start >= MIN_CHARS:
                chunks.append(self.buf[start:m.end()].strip())
                start = m.end()

        # ② Soft break if buffer grows too long
        if len(self.buf)-start > MAX_CHARS:
            cut = self.buf.rfind(' ', start+MIN_CHARS, start+MAX_CHARS) or MAX_CHARS
            chunks.append(self.buf[start:cut].strip())
            start = cut

        # ③ Time break (caller is already waiting)
        if time.monotonic() - self.last_flush > SOFT_WAIT and self.buf[start:]:
            chunks.append(self.buf[start:].strip())
            start = len(self.buf)

        # keep the tail for later
        self.buf = self.buf[start:]
        if chunks: self.last_flush = time.monotonic()
        return chunks
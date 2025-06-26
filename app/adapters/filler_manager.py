
import random

FILLERS = [
  "Let me think about that.",
  "Hmm, good question.",
  "Give me a second.",
  "Alright, here's what I think.",
  "Thinking...",
  "Let me check that for you.",
  "Just a sec.",
  "Alright, let’s see.",
  "Okay, give me a moment.",
  "Interesting... let me think.",
  "Alright, working on it.",
  "Okay, here's what I found.",
  "Sure, one moment.",
  "That's a good one.",
  "Let me find the best answer for you.",
  "Hmm... okay.",
  "Right, give me a sec.",
  "Let’s think this through.",
  "Alright, on it.",
  "Thinking it through...",
  "Let me dig into that.",
  "Here’s a thought.",
  "Now that’s something to consider.",
  "Okay, here we go.",
  "Let me explain.",
  "Sure, give me a second.",
  "Hold on a sec.",
  "Let me pull that up.",
  "Alright, just a moment.",
  "Sure, let me get back to you on that.",
  "Let’s take a look.",
  "Give me just a second.",
  "Let me try to answer that.",
  "Right, let’s go through it.",
  "Okay, let's begin with that.",
  "I think I have an idea.",
  "Processing that for you...",
  "Analyzing your question...",
  "Working on that now...",
  "Alright, just thinking...",
  "Okay, here's a possible answer.",
  "Interesting, let’s dive in.",
  "Alright, considering your input.",
  "Let me process that.",
  "Okay, good point.",
  "Let's start with this.",
  "Let’s see how to handle that.",
  "That's something I can answer.",
  "Right, give me a second to respond.",
  "Now, where do I start...",
]

class FillerManager:
    def __init__(self):
        self.pool = FILLERS.copy()
        random.shuffle(self.pool)

    def next(self) -> bytes:
        if not self.pool:                # reshape when exhausted
            self.pool = FILLERS.copy()
            random.shuffle(self.pool)
        return self.pool.pop()
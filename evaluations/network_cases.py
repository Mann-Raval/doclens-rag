"""Thirty regression prompts for the user's three networking chapters.

Expectations are review criteria, not an automatic model-quality score.
Pages are one-based PDF pages. Course PDFs are intentionally not bundled.
"""
CASES = [
    ("factual", "List the seven OSI layers in order from lowest to highest.", "All seven, physical through application; chapter 1 pp11-17."),
    ("factual", "What is the size of a UDP header and what fields does it contain?", "8 bytes (chapter 3 p5); source port, destination port, length, checksum explicitly listed in text on p6. Cite the pages supporting each part."),
    ("factual", "Explain the three steps of the TCP connection handshake.", "SYN, SYN-ACK, ACK; chapter 3 p2."),
    ("factual", "What ports do HTTP and HTTPS use by default?", "80 and 443 respectively; chapter 3 p19."),
    ("factual", "How does Stop-and-Wait flow control work?", "Send one frame, wait for acknowledgement; chapter 3 p11."),
    ("factual", "What is a VLAN?", "Logical grouping, not limited to physical connections; chapter 2 p36."),
    ("factual", "What does /24 mean in CIDR notation?", "24 network prefix bits, remaining 8 host bits; chapter 2 p35."),
    ("factual", "What are the control and data connection ports in FTP according to the notes?", "21 control and 20 data, scoped to notes; chapter 3 pp20-21."),
    ("follow-up", "Why does it wait for an acknowledgement?", "Resolve Stop-and-Wait; receiver pacing/reliability; chapter 3 p11."),
    ("follow-up", "What are its four header fields?", "Resolve UDP. Source port, destination port, length, checksum; chapter 3 p6 explicitly lists the fields."),
    ("follow-up", "Which of those two is encrypted?", "Resolve HTTP and HTTPS; HTTPS; chapter 3 p19."),
    ("follow-up", "What does the receiver send in the second step?", "Resolve TCP handshake; SYN-ACK; chapter 3 p2."),
    ("follow-up", "try again", "Regenerate comparison covering all three PDFs, not an unknown response."),
    ("summary", "Provide a detailed summary of each uploaded PDF, followed by a combined overview.", "All three: foundations; data link/network; transport/application. No invented content."),
    ("summary", "Identify and explain the main topics in each uploaded PDF.", "Explicit coverage of each PDF with supported topics."),
    ("summary", "Derive the most important takeaways from each uploaded PDF and the collection overall.", "Each PDF represented; supported takeaways."),
    ("summary", "Summarize the transport and application layer chapter.", "Focus chapter 3: TCP/UDP, flow/congestion, DNS/HTTP/FTP/email."),
    ("summary", "Give a concise overview of all documents in six bullet points.", "Six bullets, covering all three documents with citations."),
    ("comparison", "Compare the uploaded PDFs, explaining their shared ideas and important differences.", "Original failing input: all 3 docs, shared ideas, differences, complete prose and citations."),
    ("comparison", "Compare TCP and UDP using the uploaded notes.", "Reliability, connection, ordering, overhead; chapter 3 pp1-6."),
    ("comparison", "Compare HTTP and HTTPS.", "Encryption and ports, chapter 3 pp17-19."),
    ("comparison", "What is the difference between flow control and congestion control?", "Receiver capacity versus network overload; chapter 3 pp6-12."),
    ("comparison", "Compare the roles of the data link, network, and transport layers.", "Frames/MAC; packets/IP/routing; end-to-end segments; chapter 1 pp13-15."),
    ("comparison", "Compare POP3 and IMAP according to these PDFs.", "Download/local vs server-managed mail; chapter 3 pp24-26."),
    ("comparison", "Compare chapter 1 with chapter 2, focusing on scope rather than listing every topic.", "Foundation/broad survey versus data-link and network specifics; cite both."),
    ("comparison", "Compare all three documents in no more than 200 words.", "All three, shared ideas/differences, <=200 words, complete ending."),
    ("absent", "What is the Wi-Fi password for my college network?", "Explicitly unknown; no fabricated password."),
    ("absent", "What score did I get on my last networking exam?", "Explicitly unknown; no invented mark."),
    ("absent", "What is the monthly price of my home internet subscription?", "Explicitly unknown; no invented price."),
    ("absent", "What is the administrator password of the router in my room?", "Explicitly unknown; no invented credentials."),
]

FOLLOW_UP_HISTORY = {
    9: "How does Stop-and-Wait flow control work?",
    10: "What is UDP?",
    11: "What ports do HTTP and HTTPS use?",
    12: "Explain the TCP three-way handshake.",
    13: "Compare the uploaded PDFs, explaining their shared ideas and important differences.",
}

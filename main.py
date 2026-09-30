#!/usr/bin/env python3
"""
FIND A MATE - Terminal Edition
Standalone CLI adaptation of the original web project.

Run:
    python main.py

Data is persisted locally in find_a_mate.db.
No external packages are required.
"""

import os
import sqlite3
import secrets
import time
from datetime import datetime, timedelta

DB_FILE = os.path.join(os.path.dirname(__file__), "find_a_mate.db")


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def short_time(value):
    try:
        return datetime.fromisoformat(value).strftime("%d-%m-%Y %H:%M")
    except Exception:
        return value


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to continue...")


def header(title):
    clear()
    print("=" * 72)
    print(f"  FIND A MATE — {title}")
    print("=" * 72)


class App:
    def __init__(self):
        self.db = sqlite3.connect(DB_FILE)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.current_user = None
        self.init_db()

    def init_db(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            host_nickname TEXT NOT NULL,
            host_token TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            cooldown_seconds INTEGER NOT NULL DEFAULT 0,
            city TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            nickname TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            is_muted INTEGER NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            nickname TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            sender_nickname TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'text',
            content TEXT NOT NULL,
            file_name TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS member_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            nickname TEXT NOT NULL,
            role TEXT NOT NULL,
            event_type TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            left_at TEXT
        );
        """)
        self.db.commit()

    def expire_sessions(self):
        self.db.execute(
            "UPDATE sessions SET is_active=0 WHERE is_active=1 AND expires_at <= ?",
            (now_iso(),)
        )
        self.db.commit()

    def active_sessions(self):
        self.expire_sessions()
        return self.db.execute("""
            SELECT s.*,
              (SELECT COUNT(*) FROM members m WHERE m.session_id=s.id) AS member_count
            FROM sessions s
            WHERE s.is_active=1
            ORDER BY s.created_at DESC
        """).fetchall()

    def get_session(self, sid):
        self.expire_sessions()
        return self.db.execute(
            "SELECT * FROM sessions WHERE id=?", (sid,)
        ).fetchone()

    def is_member(self, sid, nickname):
        return self.db.execute(
            "SELECT * FROM members WHERE session_id=? AND nickname=?",
            (sid, nickname)
        ).fetchone()

    def is_host(self, sid, nickname):
        s = self.get_session(sid)
        return bool(s and s["host_nickname"] == nickname)

    def create_session(self):
        header("Create Study Session")
        subject = input("Subject/topic: ").strip()
        if not subject:
            print("Subject cannot be empty.")
            pause(); return

        host = input("Your nickname: ").strip()
        if not host:
            print("Nickname cannot be empty.")
            pause(); return

        try:
            duration = int(input("Duration (minutes) [60]: ").strip() or "60")
            cooldown = int(input("Message cooldown (seconds) [0]: ").strip() or "0")
        except ValueError:
            print("Please enter valid numbers.")
            pause(); return

        city = input("City (optional): ").strip() or None
        created = now_iso()
        expires = (datetime.now() + timedelta(minutes=max(1, duration))).isoformat(timespec="seconds")
        token = secrets.token_urlsafe(16)

        cur = self.db.execute("""
            INSERT INTO sessions
            (subject,host_nickname,host_token,duration_minutes,cooldown_seconds,city,
             is_active,created_at,expires_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (subject, host, token, max(1, duration), max(0, cooldown),
              city, 1, created, expires))
        sid = cur.lastrowid

        self.db.execute("""
            INSERT INTO members(session_id,nickname,role,is_muted,joined_at)
            VALUES (?,?,?,?,?)
        """, (sid, host, "host", 0, created))
        self.db.execute("""
            INSERT INTO member_history(session_id,nickname,role,event_type,joined_at)
            VALUES (?,?,?,?,?)
        """, (sid, host, "host", "joined", created))
        self.db.commit()

        self.current_user = host
        print("\nSession created successfully!")
        print(f"Session ID : {sid}")
        print(f"Host       : {host}")
        print(f"Expires    : {short_time(expires)}")
        print(f"Host token : {token}")
        print("\nShare the Session ID with students who want to join.")
        pause()
        self.session_menu(sid)

    def list_sessions(self):
        header("Available Study Sessions")
        sessions = self.active_sessions()
        if not sessions:
            print("No active sessions available.")
            pause(); return

        print(f"{'ID':<5} {'SUBJECT':<25} {'HOST':<16} {'MEMBERS':<8} {'CITY':<15}")
        print("-" * 72)
        for s in sessions:
            print(f"{s['id']:<5} {s['subject'][:24]:<25} {s['host_nickname'][:15]:<16} "
                  f"{s['member_count']:<8} {(s['city'] or '-')[:14]:<15}")
        pause()

    def request_join(self):
        header("Join Study Session")
        self.list_sessions()
        sid_text = input("\nSession ID: ").strip()
        try:
            sid = int(sid_text)
        except ValueError:
            print("Invalid session ID."); pause(); return

        s = self.get_session(sid)
        if not s or not s["is_active"]:
            print("Session not found or inactive."); pause(); return

        nickname = input("Your nickname: ").strip()
        if not nickname:
            print("Nickname cannot be empty."); pause(); return

        if self.is_member(sid, nickname):
            print("You are already a member of this session.")
            self.current_user = nickname
            pause()
            self.session_menu(sid)
            return

        existing = self.db.execute(
            "SELECT * FROM join_requests WHERE session_id=? AND nickname=?",
            (sid, nickname)
        ).fetchone()

        if existing:
            print(f"Existing request status: {existing['status']}")
            if existing["status"] == "approved":
                self.current_user = nickname
                self.session_menu(sid)
            else:
                pause()
            return

        self.db.execute("""
            INSERT INTO join_requests(session_id,nickname,status,created_at)
            VALUES (?,?,?,?)
        """, (sid, nickname, "pending", now_iso()))
        self.db.commit()
        print("Join request sent. The host must approve it.")
        print("For a local demo, the host can log in to the same session and approve it.")
        pause()

    def host_requests(self, sid):
        requests = self.db.execute("""
            SELECT * FROM join_requests
            WHERE session_id=? AND status='pending'
            ORDER BY created_at
        """, (sid,)).fetchall()
        if not requests:
            print("No pending join requests.")
            return

        print("\nPending Requests:")
        for r in requests:
            print(f"  [{r['id']}] {r['nickname']} — {short_time(r['created_at'])}")

        choice = input("Request ID to respond (Enter to cancel): ").strip()
        if not choice:
            return
        try:
            rid = int(choice)
        except ValueError:
            print("Invalid request ID."); return

        req = self.db.execute(
            "SELECT * FROM join_requests WHERE id=? AND session_id=?",
            (rid, sid)
        ).fetchone()
        if not req:
            print("Request not found."); return

        status = input("Approve or reject? [a/r]: ").strip().lower()
        if status not in ("a", "r"):
            print("Invalid choice."); return

        final = "approved" if status == "a" else "rejected"
        self.db.execute(
            "UPDATE join_requests SET status=? WHERE id=?", (final, rid)
        )

        if final == "approved":
            self.db.execute("""
                INSERT INTO members(session_id,nickname,role,is_muted,joined_at)
                VALUES (?,?,?,?,?)
            """, (sid, req["nickname"], "member", 0, now_iso()))
            self.db.execute("""
                INSERT INTO member_history(session_id,nickname,role,event_type,joined_at)
                VALUES (?,?,?,?,?)
            """, (sid, req["nickname"], "member", "joined", now_iso()))

        self.db.commit()
        print(f"Request {final}.")

    def show_members(self, sid):
        members = self.db.execute("""
            SELECT * FROM members WHERE session_id=? ORDER BY joined_at
        """, (sid,)).fetchall()
        print("\nMembers:")
        if not members:
            print("  None")
            return
        for m in members:
            state = "MUTED" if m["is_muted"] else "ACTIVE"
            print(f"  [{m['id']}] {m['nickname']} ({m['role']}) — {state}")

    def manage_members(self, sid):
        if not self.is_host(sid, self.current_user):
            print("Only the host can manage members.")
            pause(); return
        header("Member Management")
        self.show_members(sid)
        print("\n1. Mute/Unmute")
        print("2. Kick")
        print("3. Back")
        ch = input("Choice: ").strip()
        if ch == "3": return

        try:
            mid = int(input("Member ID: "))
        except ValueError:
            print("Invalid ID."); pause(); return

        member = self.db.execute(
            "SELECT * FROM members WHERE id=? AND session_id=?", (mid, sid)
        ).fetchone()
        if not member:
            print("Member not found."); pause(); return

        if ch == "1":
            new_state = 0 if member["is_muted"] else 1
            self.db.execute(
                "UPDATE members SET is_muted=? WHERE id=?", (new_state, mid)
            )
            self.db.commit()
            print("Member muted." if new_state else "Member unmuted.")
        elif ch == "2":
            if member["role"] == "host":
                print("The host cannot be kicked.")
            else:
                self.db.execute("DELETE FROM members WHERE id=?", (mid,))
                self.db.execute("""
                    UPDATE member_history
                    SET event_type='kicked', left_at=?
                    WHERE session_id=? AND nickname=? AND left_at IS NULL
                """, (now_iso(), sid, member["nickname"]))
                self.db.commit()
                print("Member kicked.")
        pause()

    def send_message(self, sid):
        nickname = self.current_user
        member = self.is_member(sid, nickname)
        if not member:
            print("You are not a member.")
            return
        if member["is_muted"]:
            print("You are muted in this session.")
            return

        s = self.get_session(sid)
        if not s or not s["is_active"]:
            print("Session is no longer active.")
            return

        # CLI demo cooldown is enforced using the last local message.
        if s["cooldown_seconds"] > 0:
            last = self.db.execute("""
                SELECT created_at FROM messages
                WHERE session_id=? AND sender_nickname=?
                ORDER BY id DESC LIMIT 1
            """, (sid, nickname)).fetchone()
            if last:
                elapsed = (datetime.now() - datetime.fromisoformat(last["created_at"])).total_seconds()
                if elapsed < s["cooldown_seconds"]:
                    print(f"Please wait {int(s['cooldown_seconds']-elapsed)+1} seconds.")
                    return

        content = input("Message: ").strip()
        if not content:
            return
        self.db.execute("""
            INSERT INTO messages(session_id,sender_nickname,type,content,created_at)
            VALUES (?,?,?,?,?)
        """, (sid, nickname, "text", content, now_iso()))
        self.db.commit()
        print("Message sent.")

    def show_chat(self, sid):
        header("Session Chat")
        messages = self.db.execute("""
            SELECT * FROM messages WHERE session_id=? ORDER BY created_at, id
        """, (sid,)).fetchall()
        if not messages:
            print("No messages yet.")
        else:
            for m in messages:
                print(f"[{short_time(m['created_at'])}] {m['sender_nickname']}: {m['content']}")
        pause()

    def stats(self, sid):
        s = self.get_session(sid)
        if not s:
            print("Session not found."); pause(); return
        members = self.db.execute(
            "SELECT COUNT(*) AS c FROM members WHERE session_id=?", (sid,)
        ).fetchone()["c"]
        messages = self.db.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id=?", (sid,)
        ).fetchone()["c"]
        pending = self.db.execute(
            "SELECT COUNT(*) AS c FROM join_requests WHERE session_id=? AND status='pending'",
            (sid,)
        ).fetchone()["c"]
        remaining = max(0, int((datetime.fromisoformat(s["expires_at"]) - datetime.now()).total_seconds()))
        print("\nSession Statistics")
        print(f"  Subject          : {s['subject']}")
        print(f"  Active           : {'Yes' if s['is_active'] else 'No'}")
        print(f"  Members          : {members}")
        print(f"  Messages         : {messages}")
        print(f"  Pending requests : {pending}")
        print(f"  Time remaining   : {remaining // 60}m {remaining % 60}s")
        pause()

    def ai_support(self, sid):
        header("Optional AI Study Support")
        print("This feature uses OPENAI_API_KEY if configured.")
        problem = input("Enter a study problem (blank to cancel): ").strip()
        if not problem:
            return
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            print("\nOPENAI_API_KEY is not configured.")
            print("Set it in your terminal environment to enable AI support.")
            pause(); return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
                input=(
                    "You are a patient study-session problem-solving partner. "
                    "Give a clear educational answer and show the reasoning at a useful level.\n\n"
                    f"Problem: {problem}"
                )
            )
            print("\nAI Solution:\n")
            print(response.output_text)
        except ImportError:
            print("Optional dependency missing. Install with: pip install openai")
        except Exception as e:
            print(f"AI request failed: {e}")
        pause()

    def end_session(self, sid):
        if not self.is_host(sid, self.current_user):
            print("Only the host can end this session.")
            pause(); return
        confirm = input("End this session? [y/N]: ").strip().lower()
        if confirm == "y":
            self.db.execute(
                "UPDATE sessions SET is_active=0 WHERE id=?", (sid,)
            )
            self.db.commit()
            print("Session ended.")
        pause()

    def session_menu(self, sid):
        while True:
            s = self.get_session(sid)
            if not s:
                print("Session not found."); pause(); return
            if not s["is_active"]:
                print("This session is inactive or expired.")
                pause(); return

            header(f"Session #{sid} — {s['subject']}")
            role = "HOST" if self.is_host(sid, self.current_user) else "MEMBER"
            print(f"User: {self.current_user} [{role}]")
            print(f"Host: {s['host_nickname']} | City: {s['city'] or '-'}")
            print(f"Expires: {short_time(s['expires_at'])}\n")

            print("1. View members")
            print("2. View chat")
            print("3. Send message")
            if role == "HOST":
                print("4. Manage join requests")
                print("5. Mute/Kick members")
                print("6. Session statistics")
                print("7. Optional AI study support")
                print("8. End session")
                print("9. Leave menu")
            else:
                print("4. Session statistics")
                print("5. Optional AI study support")
                print("6. Leave session")

            ch = input("\nChoice: ").strip()
            if ch == "1":
                self.show_members(sid); pause()
            elif ch == "2":
                self.show_chat(sid)
            elif ch == "3":
                self.send_message(sid); pause()
            elif role == "HOST" and ch == "4":
                header("Join Requests"); self.host_requests(sid); pause()
            elif role == "HOST" and ch == "5":
                self.manage_members(sid)
            elif role == "HOST" and ch == "6":
                self.stats(sid)
            elif role == "HOST" and ch == "7":
                self.ai_support(sid)
            elif role == "HOST" and ch == "8":
                self.end_session(sid); return
            elif role == "HOST" and ch == "9":
                return
            elif role != "HOST" and ch == "4":
                self.stats(sid)
            elif role != "HOST" and ch == "5":
                self.ai_support(sid)
            elif role != "HOST" and ch == "6":
                return
            else:
                print("Invalid choice.")
                pause()

    def run(self):
        while True:
            self.expire_sessions()
            header("Real-Time Study Session & Collaboration Platform")
            print("1. Create Study Session")
            print("2. Browse Active Sessions")
            print("3. Request to Join a Session")
            print("4. Exit")
            print("\nTip: Run this program in two terminals to simulate host/member workflows.")
            ch = input("\nSelect an option: ").strip()

            if ch == "1":
                self.create_session()
            elif ch == "2":
                self.list_sessions()
            elif ch == "3":
                self.request_join()
            elif ch == "4":
                self.db.close()
                print("\nThank you for using FIND A MATE!")
                break
            else:
                print("Invalid choice.")
                pause()


if __name__ == "__main__":
    App().run()

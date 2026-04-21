import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listDatasets, getDatasetInfo, type DatasetInfo } from "../api/datasets";
import "./DatasetListPage.css";

const TIMEZONES = [
  { label: "(GMT-12:00) International Date Line West", value: "Etc/GMT+12" },
  { label: "(GMT-11:00) Midway Island, Samoa", value: "Pacific/Midway" },
  { label: "(GMT-10:00) Hawaii", value: "Pacific/Honolulu" },
  { label: "(GMT-09:00) Alaska", value: "America/Anchorage" },
  { label: "(GMT-08:00) Pacific Time (US & Canada)", value: "America/Los_Angeles" },
  { label: "(GMT-07:00) Mountain Time (US & Canada)", value: "America/Denver" },
  { label: "(GMT-06:00) Central Time (US & Canada)", value: "America/Chicago" },
  { label: "(GMT-05:00) Eastern Time (US & Canada)", value: "America/New_York" },
  { label: "(GMT-04:00) Atlantic Time (Canada)", value: "America/Halifax" },
  { label: "(GMT-03:00) Buenos Aires, Georgetown", value: "America/Argentina/Buenos_Aires" },
  { label: "(GMT-02:00) Mid-Atlantic", value: "Atlantic/South_Georgia" },
  { label: "(GMT-01:00) Azores", value: "Atlantic/Azores" },
  { label: "(GMT+00:00) London, Dublin, Lisbon", value: "Europe/London" },
  { label: "(GMT+01:00) Berlin, Paris, Rome", value: "Europe/Paris" },
  { label: "(GMT+02:00) Athens, Helsinki, Istanbul", value: "Europe/Athens" },
  { label: "(GMT+03:00) Moscow, Kuwait, Riyadh", value: "Europe/Moscow" },
  { label: "(GMT+04:00) Abu Dhabi, Muscat", value: "Asia/Dubai" },
  { label: "(GMT+05:00) Islamabad, Karachi, Tashkent", value: "Asia/Karachi" },
  { label: "(GMT+05:30) Chennai, Kolkata, Mumbai", value: "Asia/Kolkata" },
  { label: "(GMT+06:00) Almaty, Dhaka", value: "Asia/Dhaka" },
  { label: "(GMT+07:00) Bangkok, Hanoi, Jakarta", value: "Asia/Bangkok" },
  { label: "(GMT+08:00) Beijing, Hong Kong, Singapore", value: "Asia/Shanghai" },
  { label: "(GMT+09:00) Seoul, Tokyo, Osaka", value: "Asia/Seoul" },
  { label: "(GMT+10:00) Sydney, Melbourne, Brisbane", value: "Australia/Sydney" },
  { label: "(GMT+11:00) Magadan, Solomon Islands", value: "Pacific/Guadalcanal" },
  { label: "(GMT+12:00) Auckland, Wellington, Fiji", value: "Pacific/Auckland" },
];

interface UserProfile {
  name: string;
  bio: string;
  pronouns: string;
  company: string;
  location: string;
  showLocalTime: boolean;
  timezone: string;
  website: string;
  social: [string, string, string, string];
}

const DEFAULT_PROFILE: UserProfile = {
  name: "GomSon-E",
  bio: "",
  pronouns: "",
  company: "",
  location: "Seoul, Korea",
  showLocalTime: true,
  timezone: "Asia/Seoul",
  website: "",
  social: ["", "", "", ""],
};

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/[\s-_]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <div className="profile-avatar">
      {initials || "?"}
    </div>
  );
}

function LocalTime() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  const h = time.getHours().toString().padStart(2, "0");
  const m = time.getMinutes().toString().padStart(2, "0");
  const offset = -time.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const oh = Math.floor(Math.abs(offset) / 60)
    .toString()
    .padStart(2, "0");
  const om = (Math.abs(offset) % 60).toString().padStart(2, "0");
  return (
    <span>
      {h}:{m} (UTC {sign}{oh}:{om})
    </span>
  );
}

function ProfileSidebar() {
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<UserProfile>(DEFAULT_PROFILE);

  function openEdit() {
    setDraft({ ...profile });
    setEditing(true);
  }

  function save() {
    setProfile({ ...draft });
    setEditing(false);
  }

  function cancel() {
    setEditing(false);
  }

  if (editing) {
    return (
      <aside className="profile-sidebar">
        <Avatar name={draft.name} />

        <div className="profile-form">
          <label className="profile-form-label">Name</label>
          <input
            className="profile-input"
            placeholder="Name"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />

          <label className="profile-form-label">Bio</label>
          <textarea
            className="profile-textarea"
            placeholder="Add a bio"
            value={draft.bio}
            onChange={(e) => setDraft({ ...draft, bio: e.target.value })}
          />

          <label className="profile-form-label">Pronouns</label>
          <select
            className="profile-select"
            value={draft.pronouns}
            onChange={(e) => setDraft({ ...draft, pronouns: e.target.value })}
          >
            <option value="">Don't specify</option>
            <option value="he/him">he/him</option>
            <option value="she/her">she/her</option>
            <option value="they/them">they/them</option>
          </select>

          <div className="profile-form-icon-row">
            <span className="profile-icon">🏢</span>
            <input
              className="profile-input profile-input-icon"
              placeholder="Company"
              value={draft.company}
              onChange={(e) => setDraft({ ...draft, company: e.target.value })}
            />
          </div>

          <div className="profile-form-icon-row">
            <span className="profile-icon">📍</span>
            <input
              className="profile-input profile-input-icon"
              placeholder="Location"
              value={draft.location}
              onChange={(e) => setDraft({ ...draft, location: e.target.value })}
            />
          </div>

          <div className="profile-form-icon-row profile-form-time-row">
            <span className="profile-icon">🕐</span>
            <div className="profile-time-group">
              <label className="profile-time-check">
                <input
                  type="checkbox"
                  checked={draft.showLocalTime}
                  onChange={(e) => setDraft({ ...draft, showLocalTime: e.target.checked })}
                />
                Display current local time
              </label>
              <select
                className="profile-select"
                value={draft.timezone}
                onChange={(e) => setDraft({ ...draft, timezone: e.target.value })}
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="profile-form-icon-row">
            <span className="profile-icon">🔗</span>
            <input
              className="profile-input profile-input-icon"
              placeholder="Website"
              value={draft.website}
              onChange={(e) => setDraft({ ...draft, website: e.target.value })}
            />
          </div>

          <label className="profile-form-label">Social accounts</label>
          {draft.social.map((val, i) => (
            <div key={i} className="profile-form-icon-row">
              <span className="profile-icon">🔗</span>
              <input
                className="profile-input profile-input-icon"
                placeholder={`Link to social profile ${i + 1}`}
                value={val}
                onChange={(e) => {
                  const next = [...draft.social] as [string, string, string, string];
                  next[i] = e.target.value;
                  setDraft({ ...draft, social: next });
                }}
              />
            </div>
          ))}

          <div className="profile-form-actions">
            <button className="btn-primary" onClick={save}>
              Save
            </button>
            <button className="btn-ghost" onClick={cancel}>
              Cancel
            </button>
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="profile-sidebar">
      <Avatar name={profile.name} />
      <div className="profile-name">{profile.name}</div>
      {profile.bio && <p className="profile-bio">{profile.bio}</p>}

      <button className="profile-edit-btn" onClick={openEdit}>
        Edit profile
      </button>

      {profile.location && (
        <div className="profile-meta-row">
          <span className="profile-meta-icon">📍</span>
          <span>{profile.location}</span>
        </div>
      )}

      {profile.showLocalTime && (
        <div className="profile-meta-row">
          <span className="profile-meta-icon">🕐</span>
          <LocalTime />
        </div>
      )}

      {profile.website && (
        <div className="profile-meta-row">
          <span className="profile-meta-icon">🔗</span>
          <a className="profile-link" href={profile.website} target="_blank" rel="noreferrer">
            {profile.website.replace(/^https?:\/\//, "")}
          </a>
        </div>
      )}
    </aside>
  );
}

export default function DatasetListPage() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    listDatasets()
      .then((summaries) =>
        Promise.allSettled(summaries.map((s) => getDatasetInfo(s.name)))
      )
      .then((results) => {
        const loaded = results
          .filter((r): r is PromiseFulfilledResult<DatasetInfo> => r.status === "fulfilled")
          .map((r) => r.value);
        setDatasets(loaded);
        if (loaded.length === 0 && results.length > 0) {
          setError("데이터셋 정보를 불러올 수 없습니다.");
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = datasets.filter((ds) =>
    ds.name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="ds-list-page">
      <nav className="navbar">
        <span className="navbar-logo">⬡ Robot Studio</span>
      </nav>

      <div className="ds-layout">
        <ProfileSidebar />

        <main className="ds-content">
          <div className="ds-content-header">
            <div className="ds-search-wrap">
              <span className="ds-search-icon">🔍</span>
              <input
                className="ds-search-input"
                placeholder="Find a dataset..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            {!loading && !error && (
              <span className="badge badge-gray">{filtered.length} datasets</span>
            )}
          </div>

          {loading && <p className="ds-state-msg">Loading...</p>}
          {error && <p className="ds-state-msg ds-state-error">Error: {error}</p>}
          {!loading && !error && filtered.length === 0 && (
            <p className="ds-state-msg">
              {query ? `"${query}"에 해당하는 데이터셋이 없습니다.` : "No datasets found."}
            </p>
          )}

          {filtered.length > 0 && (
            <div className="ds-table glass-card">
              <div className="ds-table-header">
                <span className="label">Name</span>
                <span className="label">Robot</span>
                <span className="label">FPS</span>
                <span className="label">Episodes</span>
                <span className="label">Frames</span>
                <span className="label">Successes</span>
                <span />
              </div>

              <div className="ds-table-body">
                {filtered.map((ds) => {
                  const successRate =
                    ds.total_episodes > 0
                      ? ds.total_successes / ds.total_episodes
                      : 0;
                  const successColor =
                    successRate === 1
                      ? "var(--purple)"
                      : successRate >= 0.5
                      ? "var(--warning)"
                      : "var(--danger)";

                  return (
                    <div
                      key={ds.name}
                      className="ds-row"
                      onClick={() =>
                        navigate(`/datasets/${encodeURIComponent(ds.name)}`)
                      }
                    >
                      <span className="ds-name">{ds.name}</span>
                      <span>
                        <span className="badge badge-purple">{ds.robot_type}</span>
                      </span>
                      <span className="ds-num">{ds.fps}</span>
                      <span className="ds-num">{ds.total_episodes}</span>
                      <span className="ds-num">{ds.total_frames.toLocaleString()}</span>
                      <span className="ds-num" style={{ color: successColor }}>
                        {ds.total_successes} / {ds.total_episodes}
                      </span>
                      <span className="ds-row-action">
                        <button className="ds-view-btn">보기 →</button>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

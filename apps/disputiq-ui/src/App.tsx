// =============================================================================
// MIT License
// Copyright (c) 2026 Aparavi Software AG
// =============================================================================

/**
 * Disputiq — root component rendered by the RocketRide shell.
 */

import React from 'react';
import type { ShellAppProps } from 'shell';
import { AppLayout, Documents, DocSplitLayout, DocTabs } from 'shell';

// =============================================================================
// STYLES
// =============================================================================

const styles: Record<string, React.CSSProperties> = {
	wrap: { padding: 40, fontFamily: 'var(--rr-font-family, system-ui)' },
	title: { fontSize: 22, fontWeight: 600, color: 'var(--rr-text-primary)' },
	sub: { marginTop: 8, fontSize: 13, color: 'var(--rr-text-secondary)' },
	nav: { padding: '10px 8px' },
	navItem: { padding: '6px 10px', borderRadius: 6, fontSize: 13, color: 'var(--rr-text-primary)', cursor: 'pointer' },
};

// =============================================================================
// DOCUMENTS
// =============================================================================

// The app OWNS its document model — the shell never sees it. No VFS is wired
// here, so documents are static; pass an IVirtualFileSystem to open real files.
const docs = new Documents();
docs.openStaticDocument('welcome', 'Welcome');

// =============================================================================
// COMPONENT
// =============================================================================

/** Sidebar navigation — replace the items with your app's sections. */
const SidebarNav: React.FC = () => (
	<div style={styles.nav}>
		<div style={styles.navItem}>Overview</div>
		<div style={styles.navItem}>Activity</div>
		<div style={styles.navItem}>Settings</div>
	</div>
);

/** Client-area content — replace with your app. */
const Content: React.FC<ShellAppProps> = ({ isConnected, identity }) => (
	<div style={styles.wrap}>
		<h1 style={styles.title}>Disputiq</h1>
		<p style={styles.sub}>Edit src/App.tsx and save — the preview reloads automatically.</p>
		<p style={styles.sub}>Connected: {isConnected ? 'yes' : 'no'} · User: {identity?.displayName ?? 'not signed in'}</p>
	</div>
);

/**
 * Root view — AppLayout declares the frame the wizard selected; recompose
 * its props (`sidebar`, `showStatus`) to change it.
 */
const App: React.FC<ShellAppProps> = (props) => (
	<AppLayout sidebar={<SidebarNav />} showStatus>
		<DocSplitLayout
			docs={docs}
			renderPane={(groupId) => (
				<>
					<DocTabs docs={docs} groupId={groupId} isActive />
					<Content {...props} />
				</>
			)}
		/>
	</AppLayout>
);

export default App;

import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';

import { AdminUsersComponent } from '@features/admin/users/admin-users.component';
import { AdminApiService } from '@core/services/admin-api.service';
import { AuthService } from '@core/services/auth.service';
import { UserProfile } from '@core/models/user.model';

const usersForAdminViewer: UserProfile[] = [
  {
    uid: 'target-uid',
    email: 'them@example.com',
    display_name: 'Them',
    role: 'USER',
    approved: true
  }
];

const usersForSuperAdminViewer: UserProfile[] = [
  {
    uid: 'target-uid',
    email: 'them@example.com',
    display_name: 'Them',
    role: 'USER',
    approved: true
  },
  {
    uid: 'other-admin-uid',
    email: 'other-admin@example.com',
    display_name: 'Other',
    role: 'ADMIN',
    approved: true
  }
];

function renderPage(
  viewerRole: 'ADMIN' | 'SUPER_ADMIN',
  users: UserProfile[],
  overrides: Partial<{
    listUsers: jest.Mock;
    updateRole: jest.Mock;
    deleteUser: jest.Mock;
    approveUser: jest.Mock;
  }> = {}
) {
  const listUsers = overrides.listUsers ?? jest.fn().mockReturnValue(of(users));
  const updateRole = overrides.updateRole ?? jest.fn();
  const deleteUser = overrides.deleteUser ?? jest.fn().mockReturnValue(of(undefined));
  const approveUser = overrides.approveUser ?? jest.fn();

  return render(AdminUsersComponent, {
    providers: [
      { provide: AdminApiService, useValue: { listUsers, updateRole, deleteUser, approveUser } },
      {
        provide: AuthService,
        useValue: {
          profile: () => ({ uid: 'viewer-uid', role: viewerRole }),
          role: () => viewerRole
        }
      }
    ]
  }).then((result) => ({ result, listUsers, updateRole, deleteUser, approveUser }));
}

describe('AdminUsersComponent', () => {
  it('lists the accounts the backend returned', async () => {
    await renderPage('ADMIN', usersForAdminViewer);

    expect(await screen.findByText('them@example.com')).toBeTruthy();
  });

  it('gives an ADMIN viewer no role selector, but a delete button for a USER account', async () => {
    await renderPage('ADMIN', usersForAdminViewer);

    await screen.findByText('them@example.com');
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.getByRole('button', { name: /delete/i })).toBeTruthy();
  });

  it('lets an ADMIN delete a USER account after confirming', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const { deleteUser } = await renderPage('ADMIN', usersForAdminViewer);

    await screen.findByText('them@example.com');
    const targetRow = screen.getByText('them@example.com').closest('tr') as HTMLElement;

    const user = userEvent.setup();
    await user.click(within(targetRow).getByRole('button', { name: /delete/i }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(deleteUser).toHaveBeenCalledWith('target-uid');

    confirmSpy.mockRestore();
  });

  it('never offers an ADMIN a delete button for a non-USER row, matching the backend rule', async () => {
    await renderPage('ADMIN', [
      ...usersForAdminViewer,
      {
        uid: 'admin-row-uid',
        email: 'other-admin@example.com',
        display_name: 'Other',
        role: 'ADMIN',
        approved: true
      }
    ]);

    await screen.findByText('other-admin@example.com');
    const adminRow = screen.getByText('other-admin@example.com').closest('tr') as HTMLElement;
    expect(within(adminRow).queryByRole('button', { name: /delete/i })).toBeNull();
  });

  it('lets a SUPER_ADMIN promote a USER to ADMIN, offering only USER and ADMIN', async () => {
    const { updateRole } = await renderPage('SUPER_ADMIN', usersForSuperAdminViewer, {
      updateRole: jest.fn().mockReturnValue(of({ ...usersForSuperAdminViewer[0], role: 'ADMIN' }))
    });

    await screen.findByText('them@example.com');
    const targetRow = screen.getByText('them@example.com').closest('tr') as HTMLElement;
    const select = within(targetRow).getByRole('combobox') as HTMLSelectElement;

    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual(['USER', 'ADMIN']);

    const user = userEvent.setup();
    await user.selectOptions(select, 'ADMIN');

    expect(updateRole).toHaveBeenCalledWith('target-uid', 'ADMIN');
  });

  it("does not offer a role selector or delete button for the SUPER_ADMIN's own row", async () => {
    await renderPage('SUPER_ADMIN', [
      ...usersForSuperAdminViewer,
      {
        uid: 'viewer-uid',
        email: 'me@example.com',
        display_name: 'Me',
        role: 'ADMIN',
        approved: true
      }
    ]);

    await screen.findByText('me@example.com');
    const ownRow = screen.getByText('me@example.com').closest('tr') as HTMLElement;
    expect(within(ownRow).queryByRole('combobox')).toBeNull();
    expect(within(ownRow).queryByRole('button', { name: /delete/i })).toBeNull();
  });

  it('shows an error message when the role update fails', async () => {
    await renderPage('SUPER_ADMIN', usersForSuperAdminViewer, {
      updateRole: jest.fn().mockReturnValue(throwError(() => new Error('nope')))
    });

    await screen.findByText('them@example.com');
    const targetRow = screen.getByText('them@example.com').closest('tr') as HTMLElement;
    const select = within(targetRow).getByRole('combobox');

    const user = userEvent.setup();
    await user.selectOptions(select, 'ADMIN');

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not update/i);
  });

  it('lets a SUPER_ADMIN delete an account after confirming', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const { deleteUser } = await renderPage('SUPER_ADMIN', usersForSuperAdminViewer);

    await screen.findByText('them@example.com');
    const targetRow = screen.getByText('them@example.com').closest('tr') as HTMLElement;

    const user = userEvent.setup();
    await user.click(within(targetRow).getByRole('button', { name: /delete/i }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(deleteUser).toHaveBeenCalledWith('target-uid');
    expect(screen.queryByText('them@example.com')).toBeNull();

    confirmSpy.mockRestore();
  });

  it('does not delete when the confirmation is declined', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    const { deleteUser } = await renderPage('SUPER_ADMIN', usersForSuperAdminViewer);

    await screen.findByText('them@example.com');
    const targetRow = screen.getByText('them@example.com').closest('tr') as HTMLElement;

    const user = userEvent.setup();
    await user.click(within(targetRow).getByRole('button', { name: /delete/i }));

    expect(deleteUser).not.toHaveBeenCalled();
    expect(screen.getByText('them@example.com')).toBeTruthy();

    confirmSpy.mockRestore();
  });

  it('shows an error message when the delete fails', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    await renderPage('SUPER_ADMIN', usersForSuperAdminViewer, {
      deleteUser: jest.fn().mockReturnValue(throwError(() => new Error('nope')))
    });

    await screen.findByText('them@example.com');
    const targetRow = screen.getByText('them@example.com').closest('tr') as HTMLElement;

    const user = userEvent.setup();
    await user.click(within(targetRow).getByRole('button', { name: /delete/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not delete/i);

    jest.restoreAllMocks();
  });

  it('shows a status message while loading', async () => {
    const listUsers = jest.fn().mockReturnValue(of(usersForAdminViewer));
    await renderPage('ADMIN', usersForAdminViewer, { listUsers });

    expect(listUsers).toHaveBeenCalled();
  });

  it('shows a total users KPI but no total admins KPI for an ADMIN viewer', async () => {
    await renderPage('ADMIN', usersForAdminViewer);

    await screen.findByText('them@example.com');
    expect(screen.getByText('Total users')).toBeTruthy();
    expect(screen.queryByText('Total admins')).toBeNull();
  });

  it('shows both KPIs, correctly counted, for a SUPER_ADMIN viewer', async () => {
    await renderPage('SUPER_ADMIN', usersForSuperAdminViewer);

    await screen.findByText('them@example.com');
    const usersKpi = screen.getByText('Total users').closest('.admin-kpi') as HTMLElement;
    const adminsKpi = screen.getByText('Total admins').closest('.admin-kpi') as HTMLElement;

    expect(within(usersKpi).getByText('1')).toBeTruthy();
    expect(within(adminsKpi).getByText('1')).toBeTruthy();
  });

  it('shows an Approve button for a pending USER row and counts it in the KPI', async () => {
    await renderPage('ADMIN', [
      {
        uid: 'pending-uid',
        email: 'pending@example.com',
        display_name: null,
        role: 'USER',
        approved: false
      }
    ]);

    await screen.findByText('pending@example.com');
    expect(screen.getByText('Pending approval').closest('.admin-kpi')).toHaveTextContent('1');
    expect(screen.getByRole('button', { name: /approve/i })).toBeTruthy();
  });

  it('lets an ADMIN approve a pending USER, replacing the row with Approved', async () => {
    const { approveUser } = await renderPage(
      'ADMIN',
      [
        {
          uid: 'pending-uid',
          email: 'pending@example.com',
          display_name: null,
          role: 'USER',
          approved: false
        }
      ],
      {
        approveUser: jest.fn().mockReturnValue(
          of({
            uid: 'pending-uid',
            email: 'pending@example.com',
            display_name: null,
            role: 'USER',
            approved: true
          })
        )
      }
    );

    await screen.findByText('pending@example.com');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /approve/i }));

    expect(approveUser).toHaveBeenCalledWith('pending-uid');
    expect(await screen.findByText('Approved')).toBeTruthy();
  });

  it('never offers an ADMIN an approve button for a pending ADMIN row', async () => {
    await renderPage('ADMIN', [
      {
        uid: 'pending-admin-uid',
        email: 'pending-admin@example.com',
        display_name: null,
        role: 'ADMIN',
        approved: false
      }
    ]);

    await screen.findByText('pending-admin@example.com');
    expect(screen.queryByRole('button', { name: /approve/i })).toBeNull();
    expect(screen.getByText('Pending')).toBeTruthy();
  });

  it('shows an error message when approving fails', async () => {
    await renderPage(
      'ADMIN',
      [
        {
          uid: 'pending-uid',
          email: 'pending@example.com',
          display_name: null,
          role: 'USER',
          approved: false
        }
      ],
      { approveUser: jest.fn().mockReturnValue(throwError(() => new Error('nope'))) }
    );

    await screen.findByText('pending@example.com');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /approve/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not approve/i);
  });
});

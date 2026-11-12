from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from accounts.models import User, Role
from projects.models import Project, ProjectMember, ProjectInvitation, ProjectRole, ProjectDataset, ProjectQuestion
from projects.services import ensure_personal_project, parse_csv_sample


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProjectTests(TestCase):

    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", password="password123456!", role=Role.DATA_SCIENTIST)
        self.bob = User.objects.create_user(email="bob@example.com", password="password123456!", role=Role.DATA_SCIENTIST)
        self.charlie = User.objects.create_user(email="charlie@example.com", password="password123456!", role=Role.REVIEWER)

    def test_personal_project_auto_created(self):
        self.client.force_login(self.alice)
        response = self.client.get("/projects/")
        self.assertEqual(response.status_code, 200)
        alice_project = Project.objects.filter(owner=self.alice).first()
        self.assertIsNotNone(alice_project)
        self.assertIn("Alice", alice_project.name)
        self.assertEqual(alice_project.user_role(self.alice), ProjectRole.OWNER)

    def test_create_private_project(self):
        self.client.force_login(self.alice)
        response = self.client.post("/projects/create", {"name": "Churn Prediction"}, follow=True)
        self.assertEqual(response.status_code, 200)
        project = Project.objects.filter(name="Churn Prediction").first()
        self.assertIsNotNone(project)
        self.assertEqual(project.owner, self.alice)

    def test_invite_collaborator_and_accept(self):
        self.client.force_login(self.alice)
        project = Project.objects.create(name="Team Project", owner=self.alice)
        ProjectMember.objects.create(project=project, user=self.alice, role=ProjectRole.OWNER)

        # Alice invites Bob as Data Scientist
        self.client.post(f"/projects/{project.id}/invite", {
            "email": "bob@example.com",
            "role": ProjectRole.DATA_SCIENTIST,
        })
        invite = ProjectInvitation.objects.filter(email="bob@example.com", project=project).first()
        self.assertIsNotNone(invite)
        self.assertEqual(invite.status, ProjectInvitation.Status.PENDING)

        # Bob logs in and accepts invitation
        self.client.force_login(self.bob)
        self.client.post(f"/projects/invitations/{invite.id}/accept", follow=True)
        self.assertTrue(project.members.filter(user=self.bob, role=ProjectRole.DATA_SCIENTIST).exists())

    def test_moderator_cannot_invite_moderator(self):
        project = Project.objects.create(name="Mod Project", owner=self.alice)
        ProjectMember.objects.create(project=project, user=self.alice, role=ProjectRole.OWNER)
        ProjectMember.objects.create(project=project, user=self.bob, role=ProjectRole.MODERATOR)

        self.client.force_login(self.bob)
        response = self.client.post(f"/projects/{project.id}/invite", {
            "email": "charlie@example.com",
            "role": ProjectRole.MODERATOR,
        }, follow=True)
        self.assertFalse(ProjectInvitation.objects.filter(email="charlie@example.com", role=ProjectRole.MODERATOR).exists())

    def test_transfer_ownership_and_delete_project(self):
        project = Project.objects.create(name="Old Project", owner=self.alice)
        ProjectMember.objects.create(project=project, user=self.alice, role=ProjectRole.OWNER)
        ProjectMember.objects.create(project=project, user=self.bob, role=ProjectRole.DATA_SCIENTIST)

        self.client.force_login(self.alice)
        # Transfer ownership
        self.client.post(f"/projects/{project.id}/transfer", {"new_owner_id": self.bob.id}, follow=True)
        project.refresh_from_db()
        self.assertEqual(project.owner, self.bob)

        # Bob deletes project with wrong confirmation -> rejected
        self.client.force_login(self.bob)
        self.client.post(f"/projects/{project.id}/delete", {"confirmation": "WRONG_NAME"})
        self.assertTrue(Project.objects.filter(id=project.id).exists())

        # Bob deletes project with correct confirmation -> deleted
        self.client.post(f"/projects/{project.id}/delete", {"confirmation": "Old Project"}, follow=True)
        self.assertFalse(Project.objects.filter(id=project.id).exists())

    def test_csv_upload_and_preview(self):
        project = Project.objects.create(name="CSV Project", owner=self.alice)
        ProjectMember.objects.create(project=project, user=self.alice, role=ProjectRole.OWNER)

        self.client.force_login(self.alice)
        csv_content = b"age,income,churn\n25,50000,0\n30,65000,1\n"
        uploaded_file = SimpleUploadedFile("data.csv", csv_content, content_type="text/csv")

        response = self.client.post(f"/projects/{project.id}/upload", {"file": uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        dataset = ProjectDataset.objects.filter(project=project).first()
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.row_count, 2)
        self.assertEqual(dataset.column_names, ["age", "income", "churn"])

    def test_ask_question_chat(self):
        project = Project.objects.create(name="Chat Project", owner=self.alice)
        ProjectMember.objects.create(project=project, user=self.alice, role=ProjectRole.OWNER)

        self.client.force_login(self.alice)
        self.client.post(f"/projects/{project.id}/ask", {
            "prompt": "What is the correlation between age and income?",
            "dataset_name": "data.csv",
        }, follow=True)

        question = ProjectQuestion.objects.filter(project=project).first()
        self.assertIsNotNone(question)
        self.assertEqual(question.question, "What is the correlation between age and income?")

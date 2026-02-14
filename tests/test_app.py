"""
Test suite for the Mergington High School Activities API
"""
import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": activity["description"],
            "schedule": activity["schedule"],
            "max_participants": activity["max_participants"],
            "participants": activity["participants"].copy()
        }
        for name, activity in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name in activities:
        activities[name]["participants"] = original_activities[name]["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_200(self, client):
        """Test that getting activities returns 200 OK"""
        response = client.get("/activities")
        assert response.status_code == 200
    
    def test_get_activities_returns_dict(self, client):
        """Test that activities endpoint returns a dictionary"""
        response = client.get("/activities")
        data = response.json()
        assert isinstance(data, dict)
    
    def test_get_activities_contains_expected_activities(self, client):
        """Test that response contains expected activities"""
        response = client.get("/activities")
        data = response.json()
        
        expected_activities = [
            "Basketball", "Tennis", "Drama Club", "Art Studio",
            "Debate Team", "Science Club", "Chess Club", 
            "Programming Class", "Gym Class"
        ]
        
        for activity in expected_activities:
            assert activity in data
    
    def test_activity_has_required_fields(self, client):
        """Test that each activity has all required fields"""
        response = client.get("/activities")
        data = response.json()
        
        required_fields = ["description", "schedule", "max_participants", "participants"]
        
        for activity_name, activity_data in data.items():
            for field in required_fields:
                assert field in activity_data, f"{activity_name} missing {field}"
    
    def test_participants_is_list(self, client):
        """Test that participants field is a list"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_data in data.items():
            assert isinstance(activity_data["participants"], list)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_for_existing_activity(self, client):
        """Test successful signup for an existing activity"""
        response = client.post(
            "/activities/Basketball/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200
        assert "Signed up test@mergington.edu for Basketball" in response.json()["message"]
    
    def test_signup_adds_participant_to_list(self, client):
        """Test that signup actually adds participant to the activity"""
        email = "newstudent@mergington.edu"
        client.post(f"/activities/Tennis/signup?email={email}")
        
        response = client.get("/activities")
        data = response.json()
        assert email in data["Tennis"]["participants"]
    
    def test_signup_for_nonexistent_activity(self, client):
        """Test signup for a non-existent activity returns 404"""
        response = client.post(
            "/activities/Swimming/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_duplicate_signup_returns_400(self, client):
        """Test that signing up twice returns 400 error"""
        email = "duplicate@mergington.edu"
        
        # First signup should succeed
        response1 = client.post(f"/activities/Basketball/signup?email={email}")
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(f"/activities/Basketball/signup?email={email}")
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"].lower()
    
    def test_signup_with_special_characters_in_activity_name(self, client):
        """Test signup works with URL-encoded activity names"""
        response = client.post(
            "/activities/Drama%20Club/signup?email=actor@mergington.edu"
        )
        assert response.status_code == 200


class TestRemoveParticipant:
    """Tests for DELETE /activities/{activity_name}/participants/{email} endpoint"""
    
    def test_remove_existing_participant(self, client):
        """Test removing an existing participant"""
        # First, add a participant
        email = "removeme@mergington.edu"
        client.post(f"/activities/Basketball/signup?email={email}")
        
        # Then remove them
        response = client.delete(f"/activities/Basketball/participants/{email}")
        assert response.status_code == 200
        assert f"Removed {email} from Basketball" in response.json()["message"]
    
    def test_remove_participant_actually_removes_from_list(self, client):
        """Test that removing a participant actually removes them from the list"""
        # Add a participant
        email = "temporary@mergington.edu"
        client.post(f"/activities/Tennis/signup?email={email}")
        
        # Verify they're in the list
        response = client.get("/activities")
        assert email in response.json()["Tennis"]["participants"]
        
        # Remove them
        client.delete(f"/activities/Tennis/participants/{email}")
        
        # Verify they're gone
        response = client.get("/activities")
        assert email not in response.json()["Tennis"]["participants"]
    
    def test_remove_nonexistent_participant(self, client):
        """Test removing a participant who isn't signed up returns 404"""
        response = client.delete(
            "/activities/Basketball/participants/nothere@mergington.edu"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_remove_participant_from_nonexistent_activity(self, client):
        """Test removing participant from non-existent activity returns 404"""
        response = client.delete(
            "/activities/Swimming/participants/test@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_remove_with_special_characters(self, client):
        """Test removal works with URL-encoded names and emails"""
        # Add a participant to Drama Club
        email = "special+email@mergington.edu"
        client.post(f"/activities/Drama%20Club/signup?email={email}")
        
        # Remove them using URL encoding
        response = client.delete(
            f"/activities/Drama%20Club/participants/{email.replace('+', '%2B')}"
        )
        assert response.status_code == 200


class TestIntegration:
    """Integration tests for the full workflow"""
    
    def test_full_signup_and_removal_workflow(self, client):
        """Test full workflow: view activities, signup, verify, remove, verify"""
        email = "workflow@mergington.edu"
        activity_name = "Science Club"
        
        # Get initial participant count
        response = client.get("/activities")
        initial_count = len(response.json()[activity_name]["participants"])
        
        # Sign up
        signup_response = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert signup_response.status_code == 200
        
        # Verify participant was added
        response = client.get("/activities")
        assert len(response.json()[activity_name]["participants"]) == initial_count + 1
        assert email in response.json()[activity_name]["participants"]
        
        # Remove participant
        remove_response = client.delete(f"/activities/{activity_name}/participants/{email}")
        assert remove_response.status_code == 200
        
        # Verify participant was removed
        response = client.get("/activities")
        assert len(response.json()[activity_name]["participants"]) == initial_count
        assert email not in response.json()[activity_name]["participants"]
    
    def test_multiple_signups_different_activities(self, client):
        """Test that a student can sign up for multiple activities"""
        email = "multisport@mergington.edu"
        
        # Sign up for multiple activities
        client.post(f"/activities/Basketball/signup?email={email}")
        client.post(f"/activities/Tennis/signup?email={email}")
        client.post(f"/activities/Chess Club/signup?email={email}")
        
        # Verify they're in all three
        response = client.get("/activities")
        data = response.json()
        assert email in data["Basketball"]["participants"]
        assert email in data["Tennis"]["participants"]
        assert email in data["Chess Club"]["participants"]
